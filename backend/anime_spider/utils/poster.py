"""海报下载器 - 下载并验证海报图片"""

import logging
import requests
from io import BytesIO
from PIL import Image
from urllib.parse import urlparse

from utils.cdn_upload import (
    is_cdn_public_url,
    poster_content_type,
    upload_bytes_to_cdn,
)

logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_TIMEOUT = 15
MIN_WIDTH = 200
MIN_HEIGHT = 300

BROWSER_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
    'Sec-Fetch-Dest': 'image',
    'Sec-Fetch-Mode': 'no-cors',
    'Sec-Fetch-Site': 'cross-site',
}

DOUBAN_POSTER_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Referer': 'https://movie.douban.com/',
    'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120"',
    'sec-ch-ua-mobile': '?0',
    'sec-fetch-dest': 'image',
    'sec-fetch-mode': 'no-cors',
    'sec-fetch-site': 'cross-site',
}


def build_douban_poster_headers():
    """构建豆瓣/豆瓣图片 CDN 海报下载请求头。"""
    return dict(DOUBAN_POSTER_HEADERS)


def _build_image_headers(poster_url):
    netloc = urlparse(str(poster_url or '')).netloc.lower()
    if 'doubanio.com' in netloc or 'douban.com' in netloc:
        return build_douban_poster_headers()
    return dict(BROWSER_HEADERS)


def download_poster(poster_url, dedup_key, poster_dir=None, timeout=None, require_portrait=True):
    """下载海报图片并验证是否为竖屏

    Args:
        poster_url: 海报图片 URL
        dedup_key: 动画去重键（用作文件名）
        poster_dir: 兼容旧参数，已不再使用本地目录
        timeout: 下载超时秒数
        require_portrait: 是否要求竖屏，默认 True

    Returns:
        str: CDN 公网 URL（成功）
        None: 下载失败，或在要求竖屏时不是竖屏
    """
    if not poster_url or not dedup_key:
        return None

    timeout = timeout or DEFAULT_TIMEOUT
    if is_cdn_public_url(poster_url):
        return poster_url

    try:
        headers = _build_image_headers(poster_url)
        resp = requests.get(
            poster_url,
            timeout=timeout,
            headers=headers,
            stream=True,
        )
        resp.raise_for_status()

        # 读取图片数据
        data = resp.content
        if len(data) < 1000:
            logger.debug(
                '[Poster] 图片内容过小，跳过: url=%s status=%s type=%s bytes=%s',
                poster_url,
                resp.status_code,
                resp.headers.get('content-type'),
                len(data),
            )
            return None

        img = Image.open(BytesIO(data))
        width, height = img.size

        # 检查最小尺寸
        if width < MIN_WIDTH or height < MIN_HEIGHT:
            logger.debug(f'[Poster] 图片尺寸太小 {width}x{height}: {poster_url}')
            return None

        # 默认只保留竖屏海报；豆瓣回填可放宽此要求。
        if require_portrait and height <= width:
            logger.debug(f'[Poster] 非竖屏海报 {width}x{height}，跳过: {poster_url}')
            return None

        content_type = poster_content_type(resp.headers.get('content-type'), poster_url)
        public_url = upload_bytes_to_cdn(
            str(dedup_key),
            data,
            content_type,
            timeout=timeout,
        )
        logger.info(f'[Poster] 海报已上传 CDN: {public_url} ({width}x{height})')
        return public_url

    except requests.RequestException as e:
        response = getattr(e, 'response', None)
        logger.warning(
            '[Poster] 下载失败: url=%s status=%s type=%s error=%s',
            poster_url,
            getattr(response, 'status_code', None),
            response.headers.get('content-type') if response is not None else None,
            e,
        )
        return None
    except Exception as e:
        logger.warning(f'[Poster] 处理失败 {poster_url}: {e}')
        return None


def is_portrait(image_path):
    """检查本地图片是否为竖屏"""
    try:
        with Image.open(image_path) as img:
            w, h = img.size
            return h > w
    except Exception:
        return False
