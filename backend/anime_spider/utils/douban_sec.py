"""豆瓣 sec.douban.com challenge 处理。"""

import hashlib
import logging
import re
from urllib.parse import urljoin, urlparse

import requests
from scrapy.http import HtmlResponse

logger = logging.getLogger(__name__)


DOUBAN_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}


def is_douban_url(url):
    netloc = urlparse(str(url or '')).netloc.lower()
    return netloc == 'douban.com' or netloc.endswith('.douban.com')


def is_douban_sec_url(url):
    return urlparse(str(url or '')).netloc.lower() == 'sec.douban.com'


def resolve_douban_response(url, timeout=20):
    """请求豆瓣页面，遇到 sec challenge 时自动计算 sol 并重试目标页。"""
    session = requests.Session()
    response = session.get(
        url,
        headers=DOUBAN_HEADERS,
        allow_redirects=True,
        timeout=timeout,
    )

    if not is_douban_sec_url(response.url):
        return response

    logger.info('[Douban] 命中 sec challenge: %s', response.url)
    passed = _pass_sec_challenge(session, response, timeout=timeout)
    if not passed:
        return response

    target_url = passed.headers.get('location') or _extract_hidden_value(response.text, 'red') or url
    return session.get(
        target_url,
        headers={**DOUBAN_HEADERS, 'Referer': response.url},
        allow_redirects=True,
        timeout=timeout,
    )


def build_scrapy_html_response(request, resolved_response):
    return HtmlResponse(
        url=resolved_response.url,
        status=resolved_response.status_code,
        body=resolved_response.content,
        encoding=resolved_response.encoding or 'utf-8',
        request=request,
        headers=dict(resolved_response.headers),
    )


def _pass_sec_challenge(session, response, timeout=20):
    text = response.text
    tok = _extract_hidden_value(text, 'tok')
    cha = _extract_hidden_value(text, 'cha')
    red = _extract_hidden_value(text, 'red')
    action = _extract_form_action(text) or '/c'

    if not tok or not cha or not red:
        logger.warning('[Douban] sec challenge 缺少表单字段: %s', response.url)
        return None

    sol = _solve_challenge(cha)
    post_url = urljoin(response.url, action)
    post_response = session.post(
        post_url,
        headers={
            **DOUBAN_HEADERS,
            'Referer': response.url,
            'Origin': 'https://sec.douban.com',
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        data={
            'tok': tok,
            'cha': cha,
            'sol': str(sol),
            'red': red,
        },
        allow_redirects=False,
        timeout=timeout,
    )

    if post_response.status_code not in {301, 302, 303, 307, 308}:
        logger.warning(
            '[Douban] sec challenge 未通过: status=%s body=%s',
            post_response.status_code,
            post_response.text[:200],
        )
        return None

    if 'dbsawcv1' not in session.cookies.get_dict():
        logger.warning('[Douban] sec challenge 通过但未获得 dbsawcv1 cookie')

    return post_response


def _solve_challenge(cha, difficulty=4):
    target = '0' * difficulty
    nonce = 0
    while True:
        nonce += 1
        digest = hashlib.sha512(f'{cha}{nonce}'.encode()).hexdigest()
        if digest.startswith(target):
            return nonce


def _extract_hidden_value(html, name):
    match = re.search(
        rf'<input[^>]+name=["\']{re.escape(name)}["\'][^>]+value=["\']([^"\']*)["\']',
        html,
        flags=re.IGNORECASE,
    )
    return match.group(1) if match else None


def _extract_form_action(html):
    match = re.search(r'<form[^>]+action=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
    return match.group(1) if match else None
