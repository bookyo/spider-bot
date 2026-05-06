"""豆瓣资料补齐辅助方法。"""

import logging
import os
import re
from urllib.parse import urlparse

import requests
from scrapy.http import HtmlResponse

from anime_spider.utils.anime_detector import AnimeDetector
from anime_spider.utils.douban_sec import is_douban_login_block_response, is_douban_sec_url, resolve_douban_response

logger = logging.getLogger(__name__)

DEFAULT_SEARXNG_SEARCH_URL = 'https://s.stdlang.com/search'
DEFAULT_FRODO_API_URL = 'https://frodo.douban.com/api/v2/subject/{subject_id}'
DEFAULT_FRODO_API_KEYS = [
    '0ac44ae016490db2204ce0a042db2916',
    '054022eaeae0b00e0fc068c0c0a2102a',
]

SEARXNG_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json,text/plain,*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Origin': 'https://s.stdlang.com',
    'Referer': 'https://s.stdlang.com/search',
}

FRODO_HEADERS = {
    'User-Agent': 'MicroMessenger/',
    'Referer': 'https://servicewechat.com/wx2f9b06c1de1ccfca/91/page-frame.html',
    'Accept': 'application/json,text/plain,*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

DOUBAN_SUBJECT_PATH_RE = re.compile(r'^/(?:movie/)?subject/\d+/?$')
DOUBAN_SUBJECT_ID_RE = re.compile(r'/(?:movie/)?subject/(\d+)/?')


def build_douban_search_query(title, year=None):
    title_text = str(title or '').strip()
    if not title_text:
        return None

    year_text = str(year).strip() if year not in (None, '') else ''
    if year_text:
        return f'{title_text} {year_text} 豆瓣'
    return f'{title_text} 豆瓣'


def _build_proxy_kwargs(proxy_url):
    proxy = str(proxy_url or '').strip()
    if not proxy:
        return {}
    return {
        'proxies': {
            'http': proxy,
            'https': proxy,
        }
    }


def search_douban_subject_url(title, year=None, search_url=None, timeout=20, proxy_url=None):
    """通过 SearXNG 搜索豆瓣 subject 页。"""
    query_candidates = []
    primary_query = build_douban_search_query(title, year)
    if primary_query:
        query_candidates.append(primary_query)
    fallback_query = build_douban_search_query(title, None)
    if fallback_query and fallback_query not in query_candidates:
        query_candidates.append(fallback_query)

    if not query_candidates:
        return None

    endpoint = (search_url or DEFAULT_SEARXNG_SEARCH_URL).strip() or DEFAULT_SEARXNG_SEARCH_URL
    session = requests.Session()

    for query in query_candidates:
        try:
            response = session.post(
                endpoint,
                data={
                    'q': query,
                    'category_general': 1,
                    'pageno': 1,
                    'language': 'auto',
                    'time_range': '',
                    'safesearch': 0,
                    'format': 'json',
                },
                headers=SEARXNG_HEADERS,
                timeout=timeout,
                **_build_proxy_kwargs(proxy_url),
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.warning('[DoubanBackfill] SearXNG 搜索失败 query=%s error=%s', query, exc)
            continue

        match = _extract_douban_subject_result(payload.get('results') or [])
        if match:
            return {
                'query': query,
                'url': match,
                'raw': payload,
            }

    return None


def fetch_douban_subject_metadata(subject_url, timeout=20, proxy_url=None):
    """解析豆瓣 subject 页，返回标准元数据。"""
    resolved = resolve_douban_response(subject_url, timeout=timeout, proxy_url=proxy_url)
    response = HtmlResponse(
        url=resolved.url,
        status=resolved.status_code,
        body=resolved.content,
        encoding=resolved.encoding or 'utf-8',
        headers=dict(resolved.headers),
    )
    detector = AnimeDetector()
    metadata = detector.extract_metadata(response)
    return {
        'url': resolved.url,
        'metadata': metadata,
        'blocked': is_douban_sec_url(resolved.url) or is_douban_login_block_response(resolved) or resolved.status_code in {401, 403},
        'source': 'subject_page',
        'status_code': resolved.status_code,
    }


def fetch_douban_subject_metadata_via_api(subject_url, timeout=20, api_keys=None):
    """通过 frodo 豆瓣 API 解析 subject 元数据。"""
    subject_id = extract_douban_subject_id(subject_url)
    if not subject_id:
        raise ValueError(f'invalid douban subject url: {subject_url}')

    session = requests.Session()
    last_error = None
    for api_key in iter_frodo_api_keys(api_keys):
        try:
            response = session.get(
                DEFAULT_FRODO_API_URL.format(subject_id=subject_id),
                params={'apiKey': api_key},
                headers=FRODO_HEADERS,
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            metadata = parse_douban_frodo_subject_payload(payload)
            if not _has_meaningful_metadata(metadata):
                raise ValueError('frodo response has no usable metadata')
            return {
                'url': payload.get('url') or _normalize_subject_url(subject_url),
                'metadata': metadata,
                'raw': payload,
                'source': 'frodo_api',
                'blocked': False,
                'status_code': response.status_code,
            }
        except Exception as exc:
            last_error = exc
            logger.warning('[DoubanBackfill] frodo API 失败 subject=%s key=%s error=%s', subject_id, _mask_key(api_key), exc)

    raise RuntimeError(f'frodo API failed for subject={subject_id}: {last_error}')


def parse_douban_frodo_subject_payload(payload):
    """把 frodo subject JSON 映射成当前 anime 元数据结构。"""
    if not isinstance(payload, dict):
        return {}

    detector = AnimeDetector()
    directors = _extract_names(payload.get('directors'))
    actors = _extract_names(payload.get('actors') or payload.get('casts'))
    synopsis = detector._clean_synopsis_text(payload.get('intro') or payload.get('description'))
    poster_url = _extract_frodo_poster_url(payload)
    if poster_url:
        poster_url = detector._normalize_douban_poster_url(poster_url)

    rating = payload.get('rating') if isinstance(payload.get('rating'), dict) else {}
    metadata = {
        'title': _clean_text(payload.get('title')),
        'original_title': _clean_text(payload.get('original_title')),
        'year': detector._parse_year_value(payload.get('year') or payload.get('release_date')),
        'director': '/'.join(directors[:10]) if directors else None,
        'synopsis': synopsis[:2000] if synopsis else None,
        'voice_actors': actors[:20],
        'genres': _extract_names(payload.get('genres'))[:10],
        'poster_url': poster_url,
        'douban_rating': detector._parse_rating_value(rating.get('value') or rating.get('average')),
        'imdb_rating': _extract_frodo_imdb_rating(payload, detector),
    }
    return {key: value for key, value in metadata.items() if value not in (None, '', [])}


def extract_douban_subject_id(subject_url):
    match = DOUBAN_SUBJECT_ID_RE.search(str(subject_url or ''))
    return match.group(1) if match else None


def iter_frodo_api_keys(api_keys=None):
    raw_env = os.environ.get('DOUBAN_FRODO_API_KEYS') or ''
    env_keys = [key.strip() for key in raw_env.split(',') if key.strip()]
    candidates = api_keys or env_keys or DEFAULT_FRODO_API_KEYS
    seen = set()
    for raw_key in candidates:
        key = str(raw_key or '').strip()
        if not key or key in seen:
            continue
        seen.add(key)
        yield key


def fetch_douban_subject_poster_url(subject_url, timeout=20, proxy_url=None):
    """仅提取豆瓣 subject 页海报 URL。"""
    result = fetch_douban_subject_metadata(subject_url, timeout=timeout, proxy_url=proxy_url)
    metadata = result.get('metadata') or {}
    return metadata.get('poster_url')


def _extract_douban_subject_result(results):
    for result in results:
        url = str(result.get('url') or '').strip()
        if not url:
            continue
        if _is_douban_subject_url(url):
            return _normalize_subject_url(url)
    return None


def _is_douban_subject_url(url):
    parsed = urlparse(str(url or ''))
    netloc = parsed.netloc.lower()
    if 'douban.com' not in netloc:
        return False
    return bool(DOUBAN_SUBJECT_PATH_RE.match(parsed.path or ''))


def _normalize_subject_url(url):
    parsed = urlparse(str(url or '').strip())
    path = parsed.path or ''
    if path and not path.endswith('/'):
        path = f'{path}/'
    return parsed._replace(path=path).geturl()


def _extract_names(value):
    values = value if isinstance(value, list) else [value]
    names = []
    for item in values:
        if isinstance(item, str):
            cleaned = _clean_text(item)
            if cleaned:
                names.append(cleaned)
        elif isinstance(item, dict):
            cleaned = _clean_text(item.get('name') or item.get('title'))
            if cleaned:
                names.append(cleaned)
    return list(dict.fromkeys(names))


def _extract_frodo_poster_url(payload):
    for value in [
        payload.get('cover_url'),
        _nested_get(payload, 'pic', 'large'),
        _nested_get(payload, 'pic', 'normal'),
        _nested_get(payload, 'cover', 'image', 'large', 'url'),
        _nested_get(payload, 'cover', 'image', 'normal', 'url'),
    ]:
        url = _clean_text(value)
        if url:
            return url
    return None


def _extract_frodo_imdb_rating(payload, detector):
    for value in [
        payload.get('imdb_rating'),
        payload.get('imdb_rate'),
        payload.get('imdb_score'),
        _nested_get(payload, 'imdb', 'rating'),
        _nested_get(payload, 'imdb_info', 'rating'),
    ]:
        rating = detector._parse_rating_value(value)
        if rating is not None:
            return rating
    return None


def _nested_get(value, *keys):
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _clean_text(value):
    if value is None:
        return None
    text = re.sub(r'\s+', ' ', str(value)).strip()
    return text or None


def _has_meaningful_metadata(metadata):
    return any(metadata.get(field) for field in ('title', 'year', 'poster_url', 'synopsis', 'douban_rating'))


def _mask_key(api_key):
    key = str(api_key or '')
    if len(key) <= 8:
        return '***'
    return f'{key[:4]}...{key[-4:]}'
