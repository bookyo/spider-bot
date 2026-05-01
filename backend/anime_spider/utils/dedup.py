"""去重工具"""

import hashlib
import re
from datetime import datetime
from urllib.parse import urlparse


SEASON_PATTERNS = [
    (r'第\s*([0-9一二三四五六七八九十]+)\s*季', 'season'),
    (r'season\s*(\d+)', 'season'),
]

NOISE_PATTERNS = [
    r'\s+',
    r'[·•]',
    r'[\[\(（【].*?[\]\)）】]',
    r'^(?:正在播放|在线播放|热播中|更新至)\s*',
    r'(?:第?\d+(?:\.\d+)?[集话篇])\s*$',
    r'(?:在线播放|在线观看|全集|高清|动漫|动画)$',
]


def normalize_title(title):
    """归一化标题，降低模板后缀和噪声对去重的影响。"""
    if not title:
        return ''

    value = str(title).strip().lower()
    value = re.sub(r'\s*[-_|]\s*[^-_|]+$', '', value)

    for pattern in NOISE_PATTERNS:
        value = re.sub(pattern, '', value, flags=re.IGNORECASE)

    season = extract_season_marker(value)
    if season:
        value = re.sub(season['pattern'], '', value, flags=re.IGNORECASE)
        value = f'{value}_s{season["value"]}'

    return value.strip()


def generate_title_aliases(title, original_title=None):
    """生成标题别名，用于搜索召回。"""
    values = []
    for raw in [title, original_title]:
        normalized = normalize_title(raw)
        if normalized:
            values.append(normalized)
        if raw:
            cleaned = str(raw).strip()
            cleaned = re.sub(r'\s*[-_|]\s*[^-_|]+$', '', cleaned)
            cleaned = re.sub(r'[\[\(（【].*?[\]\)）】]', '', cleaned).strip()
            if cleaned:
                values.append(cleaned.lower())
    deduped = []
    seen = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped[:10]


def normalize_person_name(name):
    """归一化导演/主创名。"""
    if not name:
        return ''
    value = str(name).strip().lower()
    value = re.sub(r'[\s/|、,，]+', '/', value)
    return value.strip('/')


def extract_season_marker(title):
    """提取季数标记。"""
    for pattern, kind in SEASON_PATTERNS:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            raw = match.group(1)
            value = _normalize_number(raw)
            if value:
                return {'kind': kind, 'value': value, 'pattern': pattern}
    return None


def _normalize_number(raw):
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)

    zh_map = {
        '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
    }
    if raw == '十':
        return 10
    if len(raw) == 2 and raw[0] == '十' and raw[1] in zh_map:
        return 10 + zh_map[raw[1]]
    if raw in zh_map:
        return zh_map[raw]
    return None


def generate_anime_dedup_key(title, year, director):
    """生成动画去重键

    使用 title + year + director 的 MD5 哈希作为去重键。
    如果某个字段缺失，用空字符串代替。
    """
    parts = [
        normalize_title(title),
        str(year or '').strip(),
        normalize_person_name(director),
    ]
    key_str = '_'.join(parts)
    return hashlib.md5(key_str.encode('utf-8')).hexdigest()


def generate_domain_dedup_key(domain):
    """生成域名去重键"""
    return domain.lower().strip().rstrip('.')


def merge_play_sources(existing_sources, new_sources):
    """合并播放源列表（按域名去重）

    策略：
    1. 同域名的播放源只保留一份
    2. 同域名下合并分集链接（去重）
    """
    if not existing_sources:
        prepared = [_enrich_play_source(source, len(source.get('episodes', []))) for source in (new_sources or [])]
        return prepared
    if not new_sources:
        return [_enrich_play_source(source, 0) for source in existing_sources]

    # 按线路键索引现有播放源，并顺手压掉历史重复线路
    source_map = {}
    for source in existing_sources:
        key = _play_source_key(source)
        if not key:
            continue
        enriched = _enrich_play_source(source, 0)
        if key in source_map:
            source_map[key] = _merge_two_sources(source_map[key], enriched, 0)
        else:
            source_map[key] = enriched

    # 合并新的播放源
    for new_source in new_sources:
        key = _play_source_key(new_source)
        if not key:
            continue

        legacy_keys = [
            existing_key
            for existing_key, existing_source in source_map.items()
            if _should_replace_legacy_source(existing_source, new_source)
        ]
        for legacy_key in legacy_keys:
            source_map.pop(legacy_key, None)

        if key in source_map:
            # 合并分集信息
            existing_source = source_map[key]
            source_map[key] = _merge_two_sources(existing_source, new_source)
        else:
            source_map[key] = _enrich_play_source(
                new_source,
                len(new_source.get('episodes', [])),
            )

    return list(source_map.values())


def normalize_play_sources_for_storage(play_sources, anime_key=None):
    """强制重建播放源标识并折叠历史脏数据。"""
    normalized = []
    for index, source in enumerate(play_sources or []):
        prepared = _normalize_single_source(source, anime_key=anime_key, index=index)
        if prepared:
            normalized.append(prepared)

    source_map = {}
    for source in normalized:
        key = _play_source_key(source)
        if not key:
            continue

        legacy_keys = [
            existing_key
            for existing_key, existing_source in source_map.items()
            if _should_replace_legacy_source(existing_source, source)
        ]
        for legacy_key in legacy_keys:
            source_map.pop(legacy_key, None)

        enriched = _enrich_play_source(source, 0)
        if key in source_map:
            source_map[key] = _merge_two_sources(source_map[key], enriched, 0)
        else:
            source_map[key] = enriched

    return list(source_map.values())


def summarize_play_sources(play_sources):
    """跨线路按 episode 去重汇总动画总集数与最新集。"""
    play_sources = play_sources or []
    episode_map = {}
    for source in play_sources:
        for episode in source.get('episodes', []):
            key = _canonical_episode_key(episode)
            if key not in episode_map:
                episode_map[key] = episode

    normalized = sorted(episode_map.values(), key=_episode_sort_key)
    latest = normalized[-1].get('episode') if normalized else None

    return {
        'total_episode_count': len(normalized),
        'latest_episode': latest,
        'new_episode_count': sum(int(source.get('new_episode_count') or 0) for source in play_sources),
    }


def _enrich_play_source(source, new_episode_count):
    episodes = sorted(source.get('episodes', []), key=_episode_sort_key)
    latest = episodes[-1].get('episode') if episodes else None

    source['episodes'] = episodes
    source['provider_id'] = generate_provider_id(source)
    source['source_id'] = generate_source_id(source)
    source['episode_count'] = len(episodes)
    source['latest_episode'] = latest
    source['new_episode_count'] = int(new_episode_count or 0)
    if new_episode_count:
        source['last_episode_update'] = datetime.now()
    return source


def _merge_two_sources(existing_source, new_source, default_new_episode_count=None):
    existing_episodes = existing_source.get('episodes', [])
    new_episodes = new_source.get('episodes', [])

    episode_map = {}
    for ep in existing_episodes:
        key = _canonical_episode_key(ep)
        if key:
            episode_map[key] = ep

    added_count = 0
    for ep in new_episodes:
        key = _canonical_episode_key(ep)
        if key not in episode_map:
            episode_map[key] = ep
            added_count += 1
            continue

        old_ep = episode_map[key]
        old_url = str((old_ep or {}).get('url') or '').strip()
        new_url = str((ep or {}).get('url') or '').strip()
        if new_url and new_url != old_url:
            merged_ep = dict(old_ep)
            merged_ep.update(ep)
            merged_ep['previous_url'] = old_url or merged_ep.get('previous_url')
            episode_map[key] = merged_ep

    merged = dict(existing_source)
    merged['episodes'] = sorted(list(episode_map.values()), key=_episode_sort_key)

    new_identity_score = _source_identity_score(new_source)
    old_identity_score = _source_identity_score(existing_source)
    if new_identity_score > old_identity_score:
        for field in ['source_name', 'provider_key', 'provider_id', 'source_id', 'line_from', 'line_sid', 'line_id']:
            if new_source.get(field):
                merged[field] = new_source.get(field)

    new_episode_count = added_count if default_new_episode_count is None else default_new_episode_count
    return _enrich_play_source(merged, new_episode_count)


def _episode_sort_key(episode):
    raw = str((episode or {}).get('episode') or '')
    match = re.search(r'(\d+(?:\.\d+)?)', raw)
    if match:
        try:
            return (0, float(match.group(1)), raw)
        except ValueError:
            pass
    return (1, raw, raw)


def _play_source_key(source):
    normalized_source = _normalize_single_source(source)
    source_id = (normalized_source or {}).get('source_id')
    if source_id:
        return f'source:{source_id}'

    raw_url = (normalized_source or {}).get('raw_url')
    source_name = (normalized_source or {}).get('source_name')
    domain = (normalized_source or {}).get('domain', '')

    if raw_url and source_name:
        return f'raw:{raw_url}|source:{source_name}'
    if raw_url:
        return f'raw:{raw_url}'
    if domain and source_name:
        return f'domain:{domain}|source:{source_name}'
    return f'domain:{domain}' if domain else None


def _should_replace_legacy_source(existing_source, new_source):
    if not _is_legacy_source(existing_source):
        return False
    if not _has_explicit_source_identity(new_source):
        return False

    existing_raw_url = (existing_source or {}).get('raw_url')
    new_raw_url = (new_source or {}).get('raw_url')
    existing_domain = (existing_source or {}).get('domain')
    new_domain = (new_source or {}).get('domain')
    existing_anime_key = (existing_source or {}).get('anime_key')
    new_anime_key = (new_source or {}).get('anime_key')

    same_page = (
        (existing_raw_url and new_raw_url and existing_raw_url == new_raw_url) or
        (existing_domain and new_domain and existing_domain == new_domain)
    )
    same_anime = existing_anime_key and new_anime_key and existing_anime_key == new_anime_key
    if not same_page and not same_anime:
        return False

    existing_keys = {_canonical_episode_key(ep) for ep in (existing_source or {}).get('episodes', [])}
    new_keys = {_canonical_episode_key(ep) for ep in (new_source or {}).get('episodes', [])}
    if not existing_keys or not new_keys:
        return False
    return existing_keys.issubset(new_keys)


def _is_legacy_source(source):
    name = str((source or {}).get('source_name') or '').strip().lower()
    return not name or name.startswith('legacy-') or name.startswith('source-')


def _has_explicit_source_identity(source):
    name = str((source or {}).get('source_name') or '').strip().lower()
    if name and not name.startswith('legacy-') and not name.startswith('source-'):
        return True
    return bool((source or {}).get('line_id') or (source or {}).get('line_from') or (source or {}).get('line_sid'))


def _source_identity_score(source):
    score = 0
    name = str((source or {}).get('source_name') or '').strip().lower()
    if name and not name.startswith('source-') and not name.startswith('legacy-'):
        score += 2
    if (source or {}).get('line_from'):
        score += 3
    if (source or {}).get('line_sid'):
        score += 2
    if (source or {}).get('provider_key'):
        score += 2
    if (source or {}).get('provider_id'):
        score += 1
    return score


def _normalize_single_source(source, anime_key=None, index=None):
    if not source:
        return None

    normalized = dict(source)
    if anime_key and not normalized.get('anime_key'):
        normalized['anime_key'] = anime_key

    if not normalized.get('anime_key'):
        inferred_anime_key = _extract_anime_key_from_source(normalized)
        if inferred_anime_key:
            normalized['anime_key'] = inferred_anime_key

    source_name = str(normalized.get('source_name') or '').strip()
    if not source_name:
        fallback_index = (index or 0) + 1
        normalized['source_name'] = f'legacy-{fallback_index}'

    normalized['provider_id'] = generate_provider_id(normalized)
    normalized['source_id'] = generate_source_id(normalized)
    return normalized


def generate_provider_id(source):
    """为底层播放提供商生成弱关联标识。"""
    provider_key = (source or {}).get('provider_key', '')
    if provider_key:
        return f'provider:{str(provider_key).strip().lower()}'

    episode_host = _extract_episode_host(source)
    if episode_host:
        return f'provider:{episode_host}'

    raw_url = (source or {}).get('raw_url', '')
    domain = (source or {}).get('domain', '')
    base = domain or urlparse(raw_url).netloc
    return f'provider:{base.lower()}' if base else None


def generate_source_id(source):
    """为当前动画下的一条播放线路生成稳定标识。"""
    anime_key = (source or {}).get('anime_key') or _extract_anime_key_from_source(source) or ''
    provider_id = (source or {}).get('provider_id', '')
    line_id = (source or {}).get('line_id', '')
    page_host = _extract_page_host(source)
    episode_host = _extract_episode_host(source)
    use_provider_as_primary = bool(episode_host and page_host and episode_host != page_host)

    if use_provider_as_primary:
        key = f'{anime_key}|{provider_id}|{line_id}'.strip()
    else:
        raw_url = (source or {}).get('raw_url', '')
        source_name = (source or {}).get('source_name', '')
        key = f'{anime_key}|{provider_id}|{line_id}|{raw_url}|{source_name}'.strip()
    if not key:
        return None
    return hashlib.md5(key.encode('utf-8')).hexdigest()


def _extract_episode_host(source):
    for episode in (source or {}).get('episodes', []) or []:
        url = str((episode or {}).get('url') or '').strip()
        if not url:
            continue
        host = urlparse(url).netloc.lower()
        if host:
            return host
    return None


def _extract_page_host(source):
    raw_url = str((source or {}).get('raw_url') or '').strip()
    if not raw_url:
        return ''
    return urlparse(raw_url).netloc.lower()


def _extract_anime_key_from_source(source):
    for value in [
        (source or {}).get('raw_url'),
        *[(episode or {}).get('url') for episode in (source or {}).get('episodes', [])[:3]],
    ]:
        match = re.search(r'/(?:post|play)/(\d+)', str(value or ''))
        if match:
            return match.group(1)
    return None


def _canonical_episode_key(episode):
    raw = str((episode or {}).get('episode') or '').strip()
    if raw:
        match = re.search(r'(\d+(?:\.\d+)?)', raw)
        if match:
            return match.group(1)
        return raw

    url = (episode or {}).get('url', '')
    return url
