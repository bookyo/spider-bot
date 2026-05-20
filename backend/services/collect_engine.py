"""采集引擎 - 从资源站 JSON/XML 接口拉取数据并写入 anime 集合"""

import asyncio
import hashlib
import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from urllib.parse import urljoin

import httpx
from bson import ObjectId

from api.database import get_db
from anime_spider.utils.dedup import (
    extract_season_marker,
    generate_title_aliases,
    normalize_person_name,
    normalize_title,
)
from utils.cdn_upload import is_cdn_public_url, poster_content_type, upload_poster_to_cdn

logger = logging.getLogger(__name__)

# 时间范围: 按小时计，0 表示全量
TIME_RANGE: dict[str, int] = {
    'today': 24,
    '1day': 24,
    '2day': 48,
    'week': 168,
    'month': 720,
    '3month': 2160,
    'all': 0,
}

DEFAULT_POSTER_PATH = '/posters/no-poster.png'
DEFAULT_HTTP_TIMEOUT = 30.0
MAX_CONCURRENT_DETAIL = 8
DEFAULT_POSTER_RETRY = 3

def normalize_collect_range(type_value: str) -> dict[str, Any]:
    """标准化采集范围，返回 {key, hours}"""
    key = str(type_value or 'today').strip() or 'today'
    if key in TIME_RANGE:
        return {'key': key, 'hours': TIME_RANGE[key]}
    return {'key': 'today', 'hours': TIME_RANGE['today']}


def build_collect_run_options(input_data: dict[str, Any] | None = None) -> dict[str, str]:
    """从输入构建采集运行选项"""
    input_data = input_data or {}
    range_value = input_data.get('range') or input_data.get('type') or 'today'
    return {'type': normalize_collect_range(range_value)['key']}


def md5(text: str) -> str:
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def build_collect_url_hash(item: dict[str, Any]) -> str:
    """构建采集条目的去重哈希"""
    douban_id = str(item.get('vod_douban_id') or item.get('douban_id') or '').strip()
    if douban_id:
        return md5(f'douban:{douban_id}')

    source_id = str(item.get('vod_id') or item.get('id') or '').strip()
    vod_name = str(item.get('vod_name') or item.get('name') or '').strip()
    type_id = str(item.get('type_id') or item.get('tid') or '').strip()
    return md5(f'{source_id}|{vod_name}|{type_id}')


def has_meaningful_value(value: Any) -> bool:
    """判断值是否有效"""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ''
    if isinstance(value, (list, tuple)):
        return len(value) > 0
    if isinstance(value, (int, float)):
        return value > 0
    return True


def pick_preferred_string(incoming: Any, existing: Any) -> str:
    if has_meaningful_value(incoming):
        return str(incoming).strip()
    return str(existing or '').strip()


def pick_preferred_number(incoming: Any, existing: Any) -> float:
    if has_meaningful_value(incoming):
        try:
            return float(incoming)
        except (ValueError, TypeError):
            pass
    try:
        return float(existing or 0)
    except (ValueError, TypeError):
        return 0.0


def pick_preferred_boolean(incoming: Any, existing: Any) -> bool:
    return incoming is True or existing is True


def merge_play_sources(existing: list[dict], incoming: list[dict]) -> list[dict]:
    """合并播放源（按 source_name 去重，追加新分集）"""
    merged: list[dict] = []
    index_map: dict[str, int] = {}

    for source in existing:
        name = str(source.get('source_name', source.get('domain', ''))).strip()
        if not name:
            continue
        episodes = normalize_episodes(source.get('episodes', []))
        if not episodes:
            continue
        merged.append({**source, 'episodes': episodes})
        index_map[name.lower()] = len(merged) - 1

    for source in incoming:
        name = str(source.get('source_name', source.get('domain', ''))).strip()
        ep_list = normalize_episodes(source.get('episodes', []))
        if not name or not ep_list:
            continue
        key = name.lower()
        if key in index_map:
            # 合并分集；同一集地址变化时用最新地址覆盖
            current_eps = merged[index_map[key]].get('episodes', [])
            current_by_episode: dict[str, dict] = {}
            current_without_episode: dict[str, dict] = {}
            for current in current_eps:
                ep_name = str(current.get('episode', '')).strip()
                url = str(current.get('url', '')).strip()
                if ep_name:
                    current_by_episode[ep_name] = current
                elif url:
                    current_without_episode[url] = current
            for ep in ep_list:
                ep_name = str(ep.get('episode', '')).strip()
                ep_url = str(ep.get('url', '')).strip()
                if ep_name and ep_name in current_by_episode:
                    current = current_by_episode[ep_name]
                    old_url = str(current.get('url', '')).strip()
                    if ep_url and ep_url != old_url:
                        current['previous_url'] = old_url
                        current['url'] = ep_url
                    continue
                if not ep_name and ep_url and ep_url in current_without_episode:
                    continue
                if ep_url:
                    current_eps.append(ep)
            merged[index_map[key]]['episodes'] = normalize_episodes(current_eps)
        else:
            idx = len(merged)
            index_map[key] = idx
            merged.append({**source, 'episodes': ep_list})

    return merged


def normalize_episodes(episodes: list[dict]) -> list[dict]:
    """去重并标准化分集列表"""
    result: list[dict] = []
    seen: set[str] = set()
    for ep in episodes or []:
        url = str(ep.get('url', '')).strip()
        episode = str(ep.get('episode', '')).strip()
        if not url:
            continue
        key = f'{url}::{episode}'
        if key in seen:
            continue
        seen.add(key)
        normalized = dict(ep)
        normalized['episode'] = episode or ''
        normalized['url'] = url
        result.append(normalized)
    return result


def merge_tags(existing: list[str], incoming: list[str]) -> list[str]:
    merged: set[str] = set()
    for tag in existing or []:
        val = str(tag).strip()
        if val:
            merged.add(val)
    for tag in incoming or []:
        val = str(tag).strip()
        if val:
            merged.add(val)
    return list(merged)


def parse_play_urls(url_str: str, from_str: str = '') -> list[dict]:
    """将 maccms 格式的播放链接转换为 spider-for-acg 格式"""
    if not url_str:
        return []
    servers = url_str.split('$$$')
    names = (from_str or '').split('$$$')
    result = []
    for idx, server_urls in enumerate(servers):
        server_name = names[idx] if idx < len(names) else f'线路{idx + 1}'
        episodes: list[dict] = []
        parts = server_urls.split('#')
        for part in parts:
            if not part.strip():
                continue
            pair = part.split('$', 1)
            ep_name = pair[0] if len(pair) > 0 else ''
            ep_url = pair[1] if len(pair) > 1 else ''
            if ep_url.strip():
                episodes.append({'episode': ep_name.strip(), 'url': ep_url.strip()})
        if episodes:
            result.append({
                'source_name': server_name.strip(),
                'domain': '',
                'episodes': episodes,
                'quality': '',
                'raw_url': '',
            })
    return result


def build_identity_conditions(anime_data: dict) -> list[dict]:
    """构建查找已有 anime 的查询条件（按匹配优先级）"""
    conditions = []
    dedup_key = str(anime_data.get('dedup_key', '')).strip()
    douban_id = str(anime_data.get('douban_id', '')).strip()
    title = str(anime_data.get('title', '')).strip()
    normalized = str(anime_data.get('normalized_title', '')).strip()
    aliases = [str(alias).strip() for alias in (anime_data.get('aliases') or []) if str(alias).strip()]
    year = int(anime_data.get('year') or 0)
    genres = anime_data.get('genres', [])

    if dedup_key:
        conditions.append({'dedup_key': dedup_key})
    if douban_id:
        conditions.append({'douban_id': douban_id})
    if title and year > 0:
        conditions.append({'title': title, 'year': year})
    if normalized:
        conditions.append({'normalized_title': normalized})
    if aliases:
        conditions.append({'aliases': {'$in': aliases}})
    if title and genres:
        conditions.append({'title': title, 'genres': {'$in': genres}})
    if title:
        conditions.append({'title': title})
    return conditions


def find_best_existing(anime_data: dict, candidates: list[dict]) -> Optional[dict]:
    """从候选列表中找最佳匹配的已有 anime"""
    dedup_key = str(anime_data.get('dedup_key', '')).strip()
    douban_id = str(anime_data.get('douban_id', '')).strip()
    title = str(anime_data.get('title', '')).strip()
    normalized_title = str(anime_data.get('normalized_title', '')).strip() or normalize_title(title)
    year = int(anime_data.get('year') or 0)

    if dedup_key:
        for c in candidates:
            if str(c.get('dedup_key', '')).strip() == dedup_key:
                return c

    if douban_id:
        for c in candidates:
            if str(c.get('douban_id', '')).strip() == douban_id:
                return c

    if title and year > 0:
        for c in candidates:
            if str(c.get('title', '')).strip() == title and int(c.get('year') or 0) == year:
                return c

    genres = set(anime_data.get('genres', []))
    if title and genres:
        for c in candidates:
            if str(c.get('title', '')).strip() == title:
                c_genres = set(c.get('genres', []))
                if genres & c_genres:
                    return c

    if title:
        for c in candidates:
            if str(c.get('title', '')).strip() == title:
                return c

    if normalized_title:
        matched: list[tuple[int, dict]] = []
        for candidate in candidates:
            score = score_weak_match(candidate, anime_data)
            if score >= 100:
                matched.append((score, candidate))
        if matched:
            matched.sort(key=lambda value: (value[0], value[1].get('quality_score', 0.0)), reverse=True)
            return matched[0][1]

    return None


def score_weak_match(existing: dict, incoming: dict) -> int:
    existing_title = str(existing.get('normalized_title') or normalize_title(existing.get('title'))).strip()
    incoming_title = str(incoming.get('normalized_title') or normalize_title(incoming.get('title'))).strip()
    if not existing_title or not incoming_title:
        return 0

    existing_season = extract_season_marker(existing_title)
    incoming_season = extract_season_marker(incoming_title)
    if season_value(existing_season) != season_value(incoming_season):
        return 0

    existing_aliases = set(existing.get('aliases') or [])
    if existing.get('title'):
        existing_aliases.update(generate_title_aliases(existing.get('title'), existing.get('original_title')))
    incoming_aliases = set(incoming.get('aliases') or [])

    score = 0
    if existing_title == incoming_title:
        score += 100
    elif incoming_aliases.intersection(existing_aliases):
        score += 85
    else:
        return 0

    year_score = compare_year(existing.get('year'), incoming.get('year'))
    if year_score < 0:
        return 0
    score += year_score

    director_score = compare_director(existing.get('director'), incoming.get('director'))
    if director_score < 0:
        return 0
    score += director_score
    return score


def season_value(season: Optional[dict]) -> int:
    if not season:
        return 1
    return int(season.get('value') or 1)


def compare_year(left: Any, right: Any) -> int:
    if left and right:
        return 15 if str(left) == str(right) else -1
    if left or right:
        return 5
    return 0


def compare_director(left: Any, right: Any) -> int:
    left_normalized = normalize_person_name(left)
    right_normalized = normalize_person_name(right)
    if left_normalized and right_normalized:
        return 10 if left_normalized == right_normalized else -1
    if left_normalized or right_normalized:
        return 3
    return 0


def build_lookup_keys(anime_data: dict) -> list[str]:
    keys: list[str] = []
    dedup_key = str(anime_data.get('dedup_key', '')).strip()
    douban_id = str(anime_data.get('douban_id', '')).strip()
    title = str(anime_data.get('title', '')).strip()
    normalized = str(anime_data.get('normalized_title', '')).strip()
    aliases = [str(alias).strip() for alias in (anime_data.get('aliases') or []) if str(alias).strip()]
    year = int(anime_data.get('year') or 0)
    genres = list(anime_data.get('genres', []))

    if dedup_key:
        keys.append(f'dedup:{dedup_key}')
    if douban_id:
        keys.append(f'douban:{douban_id}')
    if title and year > 0:
        keys.append(f'title-year:{title}::{year}')
    if normalized:
        keys.append(f'normalized:{normalized}')
    for alias in aliases:
        keys.append(f'alias:{alias}')
    if title and genres:
        keys.append(f'title-genres:{title}::{",".join(sorted(str(g) for g in genres))}')
    if title:
        keys.append(f'title:{title}')
    return keys


def append_doc_to_lookup(lookup: dict[str, list[dict]], doc: dict) -> None:
    for key in build_lookup_keys(doc):
        bucket = lookup.setdefault(key, [])
        doc_id = str(doc.get('_id'))
        if any(str(existing.get('_id')) == doc_id for existing in bucket):
            continue
        bucket.append(doc)


def sort_types_by_id(types: list[dict]) -> list[dict]:
    """按 type_id 排序类型列表"""
    def sort_key(t: dict) -> tuple:
        tid = str(t.get('type_id', ''))
        try:
            return (0, int(tid), '')
        except ValueError:
            return (1, 0, tid)
    return sorted(types, key=sort_key)


def extract_types_from_items(items: list[dict]) -> list[dict]:
    """从条目列表中提取类型"""
    type_map: dict[str, str] = {}
    for item in items or []:
        type_id = str(item.get('type_id') or item.get('tid') or '').strip()
        type_name = str(item.get('type_name') or item.get('type') or '').strip()
        if type_id and type_id not in type_map:
            type_map[type_id] = type_name or type_id
    return sort_types_by_id([
        {'type_id': tid, 'type_name': tname} for tid, tname in type_map.items()
    ])


def normalize_top_level_json_types(raw_types: Any) -> list[dict]:
    """标准化 JSON 响应的顶层类型列表"""
    result: list[dict] = []

    if isinstance(raw_types, list):
        for item in raw_types:
            if item is None:
                continue
            if isinstance(item, str):
                result.append({'type_id': item, 'type_name': item})
                continue
            type_id = str(item.get('type_id') or item.get('id') or item.get('tid') or '').strip()
            type_name = str(item.get('type_name') or item.get('type') or item.get('name') or '').strip()
            if type_id:
                result.append({'type_id': type_id, 'type_name': type_name})
        return sort_types_by_id(result)

    if isinstance(raw_types, dict):
        for key, value in raw_types.items():
            if isinstance(value, dict):
                type_id = str(value.get('type_id') or value.get('id') or value.get('tid') or key or '').strip()
                type_name = str(value.get('type_name') or value.get('type') or value.get('name') or '').strip()
                if type_id:
                    result.append({'type_id': type_id, 'type_name': type_name})
            else:
                type_id = str(key).strip()
                type_name = str(value).strip()
                if type_id:
                    result.append({'type_id': type_id, 'type_name': type_name})
    return sort_types_by_id(result)


async def download_poster_with_retry(
    poster_url: str,
    dedup_key: str,
    retries: int = DEFAULT_POSTER_RETRY,
) -> str:
    """下载海报图片并上传 CDN，失败返回 DEFAULT_POSTER_PATH

    Args:
        poster_url: 海报图片 URL
        dedup_key: 去重键（用于文件名）
        retries: 重试次数

    Returns:
        str: CDN 公网 URL 或 DEFAULT_POSTER_PATH
    """
    if not poster_url or not dedup_key:
        logger.debug('[Poster] 无海报 URL 或去重键，使用默认图')
        return DEFAULT_POSTER_PATH
    if is_cdn_public_url(poster_url):
        return poster_url

    last_error: Optional[str] = None
    for attempt in range(1, retries + 1):
        try:
            async with httpx.AsyncClient(timeout=15.0, verify=False, follow_redirects=True) as client:
                resp = await client.get(
                    poster_url,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                                      'Chrome/124.0.0.0 Safari/537.36',
                        'Accept': 'image/avif,image/webp,image/*,*/*;q=0.8',
                        'Referer': 'https://www.google.com/',
                    },
                )
                resp.raise_for_status()
                data = resp.content

            if len(data) < 1000:
                last_error = f'图片内容过小 ({len(data)} bytes)'
                logger.debug('[Poster] %s: %s', last_error, poster_url)
                if attempt < retries:
                    await asyncio.sleep(1)
                    continue
                return DEFAULT_POSTER_PATH

            from io import BytesIO
            try:
                from PIL import Image
                img = Image.open(BytesIO(data))
            except Exception:
                pass

            content_type = poster_content_type(resp.headers.get('content-type'), poster_url)
            public_url = await upload_poster_to_cdn(
                data,
                poster_url,
                dedup_key,
                content_type=content_type,
                timeout=15,
            )
            logger.info('[Poster] 上传成功: %s → %s', poster_url[:80], public_url)
            return public_url

        except Exception as e:
            last_error = f'{type(e).__name__}: {e}' if str(e) else type(e).__name__
            logger.warning(
                '[Poster] 下载失败 (第%d/%d次): %s url=%s',
                attempt, retries, last_error, poster_url[:80],
            )
            if attempt < retries:
                await asyncio.sleep(1)

    logger.warning('[Poster] 重试耗尽，使用默认图: %s (最后错误: %s)', poster_url[:80], last_error)
    return DEFAULT_POSTER_PATH


class CollectEngine:
    """采集引擎 - 从资源站 API 拉取数据"""

    def __init__(self):
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=DEFAULT_HTTP_TIMEOUT,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                                  'Chrome/120.0.0.0 Safari/537.36',
                },
            )
        return self._http_client

    async def close(self):
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    def build_request_url(self, source: dict, params: dict[str, Any] | None = None) -> str:
        """构建请求 URL，附加参数"""
        import urllib.parse
        base = str(source.get('url', '')).strip()
        if not base:
            raise ValueError('采集源 URL 不能为空')
        parsed = list(urllib.parse.urlparse(base))
        query = dict(urllib.parse.parse_qsl(parsed[4]))
        if params:
            for k, v in params.items():
                if v is None or v == '':
                    query.pop(k, None)
                else:
                    query[k] = str(v)
        parsed[4] = urllib.parse.urlencode(sorted(query.items()))
        return urllib.parse.urlunparse(parsed)

    async def fetch_list(
        self,
        source: dict,
        page: int,
        hours: int = 0,
    ) -> dict[str, Any]:
        """拉取资源站列表"""
        params: dict[str, Any] = {'ac': 'list', 'pg': page}
        if hours > 0:
            params['h'] = hours
        appid = str(source.get('appid', '')).strip()
        appkey = str(source.get('appkey', '')).strip()
        if appid:
            params['appid'] = appid
        if appkey:
            params['appkey'] = appkey

        url = self.build_request_url(source, params)
        client = await self._get_client()
        resp = await client.get(url)
        resp.raise_for_status()
        text = resp.text

        source_type = str(source.get('type', 'json')).strip().lower()
        if source_type == 'xml':
            return self._parse_xml_list(text, page)
        return self._parse_json_list(text, page)

    async def fetch_types(self, source: dict) -> list[dict]:
        """拉取资源站的类型列表"""
        data = await self.fetch_list(source, page=1, hours=0)
        types = data.get('types', [])
        if types:
            return types
        return extract_types_from_items(data.get('list', []))

    async def fetch_detail(self, source: dict, source_vod_ids: list[str]) -> list[dict]:
        """批量拉取详情"""
        if not source_vod_ids:
            return []
        ids = ','.join(source_vod_ids)
        params: dict[str, Any] = {'ac': 'detail', 'ids': ids}
        appid = str(source.get('appid', '')).strip()
        appkey = str(source.get('appkey', '')).strip()
        if appid:
            params['appid'] = appid
        if appkey:
            params['appkey'] = appkey

        url = self.build_request_url(source, params)
        client = await self._get_client()
        resp = await client.get(url)
        resp.raise_for_status()
        text = resp.text

        source_type = str(source.get('type', 'json')).strip().lower()
        if source_type == 'xml':
            data = self._parse_xml_list(text, 1)
            return data.get('list', [])
        data = self._parse_json_list(text, 1)
        return data.get('list', [])

    def _parse_json_list(self, text: str, page: int) -> dict[str, Any]:
        """解析 JSON 列表响应"""
        data = json.loads(text)
        raw_list = data.get('list', [])
        items = raw_list if isinstance(raw_list, list) else []

        top_types = normalize_top_level_json_types(
            data.get('class') or data.get('classes') or data.get('type') or data.get('types')
        )
        types = top_types if top_types else extract_types_from_items(items)

        return {
            'list': items,
            'types': types,
            'page': int(data.get('page', page)),
            'pagecount': int(data.get('pagecount', 1)),
            'total': int(data.get('total', 0)),
        }

    def _parse_xml_list(self, text: str, page: int) -> dict[str, Any]:
        """解析 XML 列表响应"""
        root = ET.fromstring(text)

        # 查找 class/ty 下的类型
        top_types: list[dict] = []
        class_el = root.find('class')
        if class_el is not None:
            for ty_el in class_el.findall('ty'):
                type_id = ty_el.get('id', '')
                type_name = (ty_el.text or '').strip()
                if type_id:
                    top_types.append({'type_id': type_id, 'type_name': type_name})

        # 查找 list 下的 video
        items: list[dict] = []
        list_el = root.find('list')
        list_page = page
        list_pagecount = 1
        list_total = 0
        if list_el is not None:
            list_page = int(list_el.get('page', page))
            list_pagecount = int(list_el.get('pagecount', 1))
            list_total = int(list_el.get('recordcount') or list_el.get('total', 0))

            for video_el in list_el.findall('video'):
                item = self._parse_xml_video(video_el)
                items.append(item)

        types = top_types if top_types else extract_types_from_items(items)

        return {
            'list': items,
            'types': types,
            'page': list_page,
            'pagecount': list_pagecount,
            'total': list_total,
        }

    def _parse_xml_video(self, el: ET.Element) -> dict[str, Any]:
        """解析 XML 中的单个 video 元素"""

        def _text(tag: str, default: str = '') -> str:
            child = el.find(tag)
            return (child.text or '').strip() if child is not None else default

        def _cdata_text(tag: str, default: str = '') -> str:
            value = _text(tag, default)
            return re.sub(r'<!\[CDATA\[|\]\]>', '', value)

        dl_el = el.find('dl')
        dd_elements = dl_el.findall('dd') if dl_el is not None else []

        # 播放来源: dl/dd flag 优先，回退到 dt 标签
        play_from = self._extract_xml_play_from(dl_el)
        if not play_from:
            play_from = _text('dt')

        play_url = self._extract_xml_play_url(dd_elements)

        return {
            'vod_id': el.get('id', '') or _text('id'),
            'vod_name': _cdata_text('name'),
            'type_id': _text('tid'),
            'type_name': _text('type'),
            'vod_remarks': _cdata_text('note'),
            'vod_time': _text('last'),
            'pic': _text('pic'),
            'actor': _cdata_text('actor'),
            'director': _cdata_text('director'),
            'area': _text('area'),
            'year': _text('year'),
            'lang': _text('lang'),
            'content': _cdata_text('des'),
            'vod_total': _text('total'),
            'vod_isend': _text('isend', '0'),
            'vod_play_url': play_url,
            'vod_play_from': play_from,
            'note': _cdata_text('note'),
            'vod_class': _text('class'),
            'vod_tag': _text('tag'),
            'vod_score': float(_text('score') or 0),
            'vod_douban_score': float(_text('douban_score') or 0),
            'vod_douban_id': _text('douban_id'),
        }

    @staticmethod
    def _extract_xml_play_url(dd_elements: list[ET.Element]) -> str:
        """从 XML dd 元素列表提取播放链接"""
        if not dd_elements:
            return ''
        values: list[str] = []
        for dd_el in dd_elements:
            text = (dd_el.text or '').strip()
            cleaned = re.sub(r'<!\[CDATA\[|\]\]>', '', text)
            if cleaned:
                values.append(cleaned)
        return '$$$'.join(values)

    @staticmethod
    def _extract_xml_play_from(dl_el: Optional[ET.Element]) -> str:
        """从 XML dl 元素提取播放来源名"""
        if dl_el is None:
            return ''
        # 优先从 dd 子元素获取 flag 属性
        flags: list[str] = []
        for dd_el in dl_el.findall('dd'):
            flag = dd_el.get('flag', '')
            if flag and flag.strip():
                flags.append(flag.strip())
        if flags:
            return '$$$'.join(flags)
        # 回退到 dl 自身属性
        flag = dl_el.get('flag', '')
        return flag.strip()

    async def get_type_binding_map(self, source_id: Any) -> dict[str, str]:
        db = get_db()
        if db is None or source_id is None:
            return {}
        docs = await db['collect_type_bindings'].find({'collect_source': source_id}).to_list(None)
        result: dict[str, str] = {}
        for doc in docs:
            source_type_id = str(doc.get('source_type_id', '')).strip()
            local_type = str(doc.get('local_type', '')).strip()
            if source_type_id and local_type:
                result[source_type_id] = local_type
        return result

    def normalize(self, item: dict, source: dict) -> dict[str, Any]:
        """将采集源数据标准化为 anime 文档格式"""
        # 基本信息
        title = str(item.get('vod_name') or item.get('name') or '').strip()
        original_title = str(item.get('vod_en') or item.get('en') or '').strip()
        sub_title = str(item.get('vod_sub') or item.get('sub') or item.get('subname') or '').strip()

        year = 0
        try:
            year = int(item.get('vod_year') or item.get('year') or 0)
        except (ValueError, TypeError):
            pass

        # 导演/声优/简介
        director = str(item.get('vod_director') or item.get('director') or '').strip()
        actor = str(item.get('vod_actor') or item.get('actor') or '').strip()
        synopsis = str(
            item.get('vod_content') or item.get('vod_blurb') or
            item.get('content') or item.get('des') or ''
        ).strip()

        # 类型/标签
        type_id = str(item.get('type_id') or item.get('tid') or '')
        type_name = str(item.get('type_name') or item.get('type') or '')
        class_name = str(item.get('vod_class') or item.get('class') or '')
        tag_str = str(item.get('vod_tag') or item.get('tag') or '')
        tags = [t.strip() for t in tag_str.split(',') if t.strip()]
        genres: list[str] = []
        if type_name:
            genres.append(type_name)
        if class_name and class_name not in genres:
            genres.append(class_name)
        for tag in tags:
            if tag not in genres:
                genres.append(tag)

        # 海报
        poster_url = str(item.get('vod_pic') or item.get('pic') or '').strip()

        # 豆瓣信息
        douban_id = str(item.get('vod_douban_id') or item.get('douban_id') or '').strip()
        douban_rating = 0.0
        try:
            douban_rating = float(item.get('vod_douban_score') or item.get('douban_score') or 0)
        except (ValueError, TypeError):
            pass

        # 来源域名
        import urllib.parse
        source_url = str(source.get('url', '')).strip()
        domain = ''
        try:
            domain = urllib.parse.urlparse(source_url).netloc
        except Exception:
            pass

        # 播放源
        play_url_str = str(item.get('vod_play_url') or item.get('play_url') or '').strip()
        play_from_str = str(item.get('vod_play_from') or item.get('play_from') or '').strip()
        play_sources = parse_play_urls(play_url_str, play_from_str)
        # 补充 domain
        for ps in play_sources:
            if not ps.get('domain'):
                ps['domain'] = domain

        # 总集数
        total = 0
        try:
            total = int(item.get('vod_total') or item.get('total') or 0)
        except (ValueError, TypeError):
            pass

        # 是否完结
        is_end_str = str(item.get('vod_isend') or item.get('isend') or '0')
        is_end = is_end_str == '1'

        # 连载状态
        serial = str(item.get('vod_serial') or item.get('serial') or '').strip()

        # 去重键
        dedup_key = build_collect_url_hash(item)

        # 来源URL
        source_vod_id = str(item.get('vod_id') or item.get('id') or '')
        source_urls: list[str] = []
        if source_vod_id and source_url:
            source_urls.append(self.build_request_url(source, {'ac': 'detail', 'ids': source_vod_id}))

        # 别名
        aliases = generate_title_aliases(title, original_title)
        if sub_title and sub_title != title and sub_title not in aliases:
            aliases.append(sub_title)

        # 备注
        remarks = str(item.get('vod_remarks') or item.get('note') or '').strip()
        normalized_title = normalize_title(title)

        now = datetime.now(timezone.utc)

        anime_doc: dict[str, Any] = {
            'title': title,
            'original_title': original_title or None,
            'aliases': aliases,
            'normalized_title': normalized_title,
            'year': year if year > 0 else None,
            'director': director or None,
            'voice_actors': [a.strip() for a in actor.split(',') if a.strip()] if actor else [],
            'synopsis': synopsis or None,
            'poster_url': poster_url or None,
            'source_urls': source_urls,
            'source_domain': domain or None,
            'genres': genres,
            'dedup_key': dedup_key,
            'play_sources': play_sources,
            'latest_episode': None,
            'total_episode_count': total if total > 0 else None,
            'new_episode_count': 0,
            'incremental_found': False,
            'douban_id': douban_id or None,
            'douban_rating': douban_rating if douban_rating > 0 else None,
            'remarks': remarks or None,
            'discovered_at': now,
            'updated_at': now,
        }

        # 计算最新集
        latest_ep = ''
        total_eps = 0
        for ps in play_sources:
            eps = ps.get('episodes', [])
            for ep in eps:
                ep_num = str(ep.get('episode', '')).strip()
                try:
                    num = int(re.sub(r'[^0-9]', '', ep_num))
                except ValueError:
                    num = 0
                if num > total_eps:
                    total_eps = num
                    latest_ep = ep_num
        if latest_ep:
            anime_doc['latest_episode'] = latest_ep
        if total_eps > 0 and not total:
            anime_doc['total_episode_count'] = total_eps

        return anime_doc

    def apply_type_binding(
        self,
        anime_data: dict[str, Any],
        item: dict[str, Any],
        type_binding_map: dict[str, str],
    ) -> dict[str, Any]:
        if not type_binding_map:
            return anime_data

        source_type_id = str(item.get('type_id') or item.get('tid') or '').strip()
        local_type = type_binding_map.get(source_type_id, '').strip()
        if not local_type:
            return anime_data

        genres = [str(g).strip() for g in anime_data.get('genres', []) if str(g).strip()]
        if local_type not in genres:
            genres.insert(0, local_type)
        anime_data['genres'] = genres
        anime_data['collect_source_type_id'] = source_type_id
        anime_data['collect_source_type_name'] = str(item.get('type_name') or item.get('type') or '').strip() or local_type
        anime_data['collect_local_type'] = local_type
        return anime_data

    async def find_existing_anime_map(
        self,
        anime_data_list: list[dict],
    ) -> dict[str, list[dict]]:
        """根据一组 anime 数据批量查找已有文档，返回按查找键组织的映射"""
        db = get_db()
        if db is None:
            return {}

        all_conditions: list[dict] = []
        seen: set[str] = set()
        for ad in anime_data_list:
            for cond in build_identity_conditions(ad):
                key = json.dumps(cond, sort_keys=True)
                if key not in seen:
                    seen.add(key)
                    all_conditions.append(cond)

        if not all_conditions:
            return {}

        existing_docs = await db['anime'].find({'$or': all_conditions}).to_list(None)

        # 构建查找键 → 文档列表的映射
        lookup: dict[str, list[dict]] = {}
        for doc in existing_docs:
            douban_id = str(doc.get('douban_id', '')).strip()
            title = str(doc.get('title', '')).strip()
            normalized_title = str(doc.get('normalized_title', '')).strip()
            aliases = [str(alias).strip() for alias in (doc.get('aliases') or []) if str(alias).strip()]
            year = int(doc.get('year') or 0)
            genres_list = list(doc.get('genres', []))
            dedup_key = str(doc.get('dedup_key', '')).strip()

            keys = set()
            if dedup_key:
                keys.add(f'dedup:{dedup_key}')
            if douban_id:
                keys.add(f'douban:{douban_id}')
            if title and year > 0:
                keys.add(f'title-year:{title}::{year}')
            if normalized_title:
                keys.add(f'normalized:{normalized_title}')
            for alias in aliases:
                keys.add(f'alias:{alias}')
            if title and genres_list:
                keys.add(f'title-genres:{title}::{",".join(sorted(str(g) for g in genres_list))}')
            if title:
                keys.add(f'title:{title}')

            for k in keys:
                lookup.setdefault(k, []).append(doc)

        return lookup

    def resolve_existing(
        self,
        anime_data: dict,
        lookup: dict[str, list[dict]],
    ) -> Optional[dict]:
        """从查找映射中解析最佳匹配的已有文档"""
        candidates: list[dict] = []
        seen_ids: set[str] = set()

        for key in build_lookup_keys(anime_data):
            for doc in lookup.get(key, []):
                doc_id = str(doc['_id'])
                if doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    candidates.append(doc)

        return find_best_existing(anime_data, candidates)

    def merge_anime_data(self, existing: dict, incoming: dict) -> dict:
        """合并已有文档和采集到的数据"""
        merged = dict(existing)
        merged['title'] = pick_preferred_string(incoming.get('title'), existing.get('title'))
        merged['original_title'] = pick_preferred_string(
            incoming.get('original_title'), existing.get('original_title')
        ) or None
        merged['normalized_title'] = pick_preferred_string(
            incoming.get('normalized_title'), existing.get('normalized_title')
        ) or normalize_title(merged.get('title'))
        merged['director'] = pick_preferred_string(incoming.get('director'), existing.get('director')) or None
        merged['synopsis'] = pick_preferred_string(incoming.get('synopsis'), existing.get('synopsis')) or None
        merged['poster_url'] = pick_preferred_string(incoming.get('poster_url'), existing.get('poster_url')) or None
        merged['year'] = int(pick_preferred_number(incoming.get('year'), existing.get('year'))) or None
        merged['douban_id'] = pick_preferred_string(incoming.get('douban_id'), existing.get('douban_id')) or None

        incoming_rating = incoming.get('douban_rating')
        existing_rating = existing.get('douban_rating')
        if has_meaningful_value(incoming_rating):
            merged['douban_rating'] = float(incoming_rating)
        elif has_meaningful_value(existing_rating):
            merged['douban_rating'] = float(existing_rating)
        else:
            merged['douban_rating'] = None

        # 合并播放源
        merged['play_sources'] = merge_play_sources(
            existing.get('play_sources', []),
            incoming.get('play_sources', []),
        )

        # 合并类型
        merged['genres'] = merge_tags(
            existing.get('genres', []),
            incoming.get('genres', []),
        )

        # 合并别名
        existing_aliases = set(existing.get('aliases', []))
        for a in incoming.get('aliases', []):
            if a.strip():
                existing_aliases.add(a.strip())
        merged['aliases'] = list(existing_aliases)

        # 合并 source_urls
        existing_urls = set(existing.get('source_urls', []))
        for u in incoming.get('source_urls', []):
            if u.strip():
                existing_urls.add(u.strip())
        merged['source_urls'] = list(existing_urls)

        # 重新计算最新集
        latest_ep = ''
        max_ep_num = 0
        total_eps = 0
        for ps in merged.get('play_sources', []):
            for ep in ps.get('episodes', []):
                ep_num_str = str(ep.get('episode', '')).strip()
                try:
                    num = int(re.sub(r'[^0-9]', '', ep_num_str))
                except ValueError:
                    num = 0
                if num > max_ep_num:
                    max_ep_num = num
                    latest_ep = ep_num_str
                total_eps += 1
        if latest_ep:
            merged['latest_episode'] = latest_ep

        existing_total = int(existing.get('total_episode_count') or 0)
        incoming_total = int(incoming.get('total_episode_count') or 0)
        merged['total_episode_count'] = max(existing_total, incoming_total, total_eps) or None

        merged['updated_at'] = datetime.now(timezone.utc)

        # 保留不可被覆盖的字段
        for field in ('_id', 'discovered_at', 'quality_score', 'incremental_priority',
                       'last_incremental_check', 'new_episode_count', 'incremental_found',
                       'dedup_key'):
            if field not in merged and field in existing:
                merged[field] = existing[field]

        return merged

    async def run(
        self,
        source: dict,
        range_type: str = 'today',
        on_status: Optional[Callable[[dict[str, Any]], Any]] = None,
        on_progress: Optional[Callable[[dict[str, Any]], Any]] = None,
    ) -> dict[str, Any]:
        """执行采集

        Args:
            source: 采集源文档
            range_type: 采集范围 (today/1day/2day/week/month/3month/all)
            on_status: 状态回调 async fn({"message": ..., "log": ...})
            on_progress: 进度回调 async fn({"processed": ..., "created": ..., ...})
        """
        db = get_db()
        if db is None:
            raise RuntimeError('数据库未连接')

        range_info = normalize_collect_range(range_type)
        hours = range_info['hours']

        page = 1
        has_more = True
        created_count = 0
        updated_count = 0
        skipped_count = 0
        processed_count = 0
        type_binding_map = await self.get_type_binding_map(source.get('_id'))
        restrict_to_bound_types = bool(type_binding_map)

        while has_more:
            # 拉取列表
            if on_status:
                await on_status({
                    'message': f'正在拉取第 {page} 页列表',
                    'log': f'开始拉取第 {page} 页列表',
                })

            try:
                list_data = await self.fetch_list(source, page, hours)
            except Exception as e:
                logger.error(f'拉取列表失败 page={page}: {e}')
                if on_status:
                    await on_status({
                        'message': f'第 {page} 页拉取失败: {e}',
                        'log': f'第 {page} 页拉取失败: {e}',
                    })
                break

            items = list_data.get('list', [])
            if not items:
                if on_status:
                    msg = f'第 {page} 页无更多数据' if processed_count > 0 else '本次采集范围暂无数据'
                    await on_status({'message': msg, 'log': msg})
                break

            if on_status:
                await on_status({
                    'message': f'第 {page} 页列表获取完成，本页 {len(items)} 条',
                    'log': f'第 {page} 页列表获取完成，本页 {len(items)} 条',
                })

            # 检查哪些需要拉取详情
            ids_needing_detail: list[str] = []
            for item in items:
                has_play = item.get('vod_play_url') or item.get('play_url')
                if not has_play:
                    vid = str(item.get('vod_id') or item.get('id') or '').strip()
                    if vid:
                        ids_needing_detail.append(vid)

            detail_map: dict[str, dict] = {}
            if ids_needing_detail:
                try:
                    if on_status:
                        await on_status({
                            'message': f'正在拉取详情，当前 {len(ids_needing_detail)} 条',
                            'log': f'开始拉取详情 {len(ids_needing_detail)} 条',
                        })
                    details = await self.fetch_detail(source, ids_needing_detail)
                    for detail in details:
                        vid = str(detail.get('vod_id') or detail.get('id') or '').strip()
                        if vid:
                            detail_map[vid] = detail
                except Exception as e:
                    logger.error(f'拉取详情失败: {e}')

            # 标准化 + 填充详情
            prepared: list[dict] = []
            for item in items:
                source_type_id = str(item.get('type_id') or item.get('tid') or '').strip()
                if restrict_to_bound_types and source_type_id not in type_binding_map:
                    skipped_count += 1
                    continue
                vid = str(item.get('vod_id') or item.get('id') or '').strip()
                if vid in detail_map:
                    item = {**item, **detail_map[vid]}
                url_hash = build_collect_url_hash(item)
                anime_data = self.normalize(item, source)
                anime_data = self.apply_type_binding(anime_data, item, type_binding_map)
                prepared.append({
                    'url_hash': url_hash,
                    'anime_data': anime_data,
                    'source_time': str(item.get('vod_time') or item.get('last') or ''),
                })

            if not prepared:
                skipped_count += len(items)
                page += 1
                pagecount = int(list_data.get('pagecount', 1))
                if page > pagecount:
                    has_more = False
                continue

            # 查询历史记录（去重）
            url_hashes = [p['url_hash'] for p in prepared]
            history_docs = await db['collect_history'].find({
                'url_hash': {'$in': url_hashes},
            }).to_list(None)
            history_map: dict[str, dict] = {h['url_hash']: h for h in history_docs}

            # 过滤：跳过已采集且未变化的条目
            bind_enabled = source.get('bind', False)
            pending: list[dict] = []
            for entry in prepared:
                hist = history_map.get(entry['url_hash'])
                if not hist:
                    pending.append(entry)
                    continue
                # 默认允许已存在条目继续进入合并更新；仅在 bind 启用时用 source_time 做额外跳过
                if not bind_enabled:
                    pending.append(entry)
                    continue
                # bind 启用时检查 source_time 是否变化
                source_time = entry.get('source_time', '')
                history_time = str(hist.get('source_time', ''))
                if not source_time or source_time == history_time:
                    skipped_count += 1
                    continue
                pending.append(entry)

            if not pending:
                page += 1
                pagecount = int(list_data.get('pagecount', 1))
                if page > pagecount:
                    has_more = False
                continue

            # 批量查找已有 anime
            anime_data_list = [e['anime_data'] for e in pending]
            lookup = await self.find_existing_anime_map(anime_data_list)

            # 逐条处理
            for entry in pending:
                anime_data = entry['anime_data']
                existing = self.resolve_existing(anime_data, lookup)

                if existing:
                    # 已存在 → 合并更新
                    merged = self.merge_anime_data(existing, anime_data)
                    doc_id = existing['_id']
                    merged.pop('_id', None)  # remove _id for update

                    # 下载海报（已有好的 poster_local 则跳过下载）
                    existing_poster_local = existing.get('poster_local', '')
                    if existing_poster_local and existing_poster_local != DEFAULT_POSTER_PATH:
                        merged['poster_local'] = existing_poster_local
                    else:
                        poster_url_val = merged.get('poster_url') or ''
                        dedup_key = merged.get('dedup_key') or anime_data.get('dedup_key', '')
                        poster_local = await download_poster_with_retry(
                            poster_url_val,
                            dedup_key,
                        )
                        merged['poster_local'] = poster_local

                    await db['anime'].update_one(
                        {'_id': doc_id},
                        {'$set': merged},
                    )
                    append_doc_to_lookup(lookup, {'_id': doc_id, **merged})
                    updated_count += 1
                    action = 'updated'
                else:
                    # 新记录 → 插入
                    anime_data['_id'] = ObjectId()

                    # 下载海报
                    poster_url_val = anime_data.get('poster_url') or ''
                    dedup_key = anime_data.get('dedup_key', '')
                    poster_local = await download_poster_with_retry(
                        poster_url_val,
                        dedup_key,
                    )
                    anime_data['poster_local'] = poster_local

                    await db['anime'].insert_one(anime_data)
                    append_doc_to_lookup(lookup, anime_data)
                    created_count += 1
                    action = 'created'

                # 记录采集历史
                await db['collect_history'].update_one(
                    {'url_hash': entry['url_hash']},
                    {'$set': {
                        'url_hash': entry['url_hash'],
                        'collect_source': source.get('_id'),
                        'vod_name': anime_data.get('title', ''),
                        'source_time': entry.get('source_time', ''),
                        'created_at': datetime.now(timezone.utc),
                    }},
                    upsert=True,
                )

                processed_count += 1

                if on_progress:
                    await on_progress({
                        'processed': processed_count,
                        'created': created_count,
                        'updated': updated_count,
                        'skipped': skipped_count,
                        'page': page,
                        'current_name': anime_data.get('title', ''),
                        'action': action,
                    })

            page += 1
            pagecount = int(list_data.get('pagecount', 1))
            if page > pagecount:
                has_more = False

        # 更新采集源统计
        now = datetime.now(timezone.utc)
        await db['collect_sources'].update_one(
            {'_id': source['_id']},
            {'$set': {
                'last_collect': now,
                'collect_num': (source.get('collect_num', 0) or 0) + created_count + updated_count,
                'updated_at': now,
            }},
        )

        return {
            'range': range_info['key'],
            'processed': processed_count,
            'created': created_count,
            'updated': updated_count,
            'skipped': skipped_count,
            'pages': page - 1,
        }


# 导出单例
collect_engine = CollectEngine()
