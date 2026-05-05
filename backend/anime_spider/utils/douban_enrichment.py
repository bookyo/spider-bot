"""豆瓣资料补齐辅助方法。"""

import logging
import re
from urllib.parse import urlparse

import requests
from scrapy.http import HtmlResponse

from anime_spider.utils.anime_detector import AnimeDetector
from anime_spider.utils.douban_sec import resolve_douban_response

logger = logging.getLogger(__name__)

DEFAULT_SEARXNG_SEARCH_URL = 'https://s.stdlang.com/search'

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

DOUBAN_SUBJECT_PATH_RE = re.compile(r'^/(?:movie/)?subject/\d+/?$')


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
    }


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
