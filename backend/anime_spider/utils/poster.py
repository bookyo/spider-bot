"""海报下载器 - 下载并验证海报图片"""

import os
import logging
import hashlib
import requests
from io import BytesIO
from PIL import Image

logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_POSTER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'posters')
DEFAULT_TIMEOUT = 15
MIN_WIDTH = 200
MIN_HEIGHT = 300


def download_poster(poster_url, dedup_key, poster_dir=None, timeout=None):
    """下载海报图片并验证是否为竖屏

    Args:
        poster_url: 海报图片 URL
        dedup_key: 动画去重键（用作文件名）
        poster_dir: 存储目录，默认 posters/
        timeout: 下载超时秒数

    Returns:
        str: 本地文件路径（成功且为竖屏）
        None: 下载失败或非竖屏
    """
    if not poster_url or not dedup_key:
        return None

    poster_dir = poster_dir or DEFAULT_POSTER_DIR
    timeout = timeout or DEFAULT_TIMEOUT

    os.makedirs(poster_dir, exist_ok=True)

    try:
        resp = requests.get(
            poster_url,
            timeout=timeout,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
            stream=True,
        )
        resp.raise_for_status()

        # 读取图片数据
        data = resp.content
        if len(data) < 1000:
            logger.debug(f'[Poster] 图片太小，跳过: {poster_url}')
            return None

        img = Image.open(BytesIO(data))
        width, height = img.size

        # 检查最小尺寸
        if width < MIN_WIDTH or height < MIN_HEIGHT:
            logger.debug(f'[Poster] 图片尺寸太小 {width}x{height}: {poster_url}')
            return None

        # 只保留竖屏海报 (height > width)
        if height <= width:
            logger.debug(f'[Poster] 非竖屏海报 {width}x{height}，跳过: {poster_url}')
            return None

        # 确定文件格式
        fmt = img.format or 'JPEG'
        ext = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp', 'GIF': 'gif'}.get(fmt, 'jpg')

        # 文件名: dedup_key + url hash（避免同一 dedup_key 不同海报覆盖）
        url_hash = hashlib.md5(poster_url.encode()).hexdigest()[:8]
        filename = f'{dedup_key}_{url_hash}.{ext}'
        filepath = os.path.join(poster_dir, filename)

        # 保存图片
        with open(filepath, 'wb') as f:
            f.write(data)

        logger.info(f'[Poster] 海报已保存: {filepath} ({width}x{height})')
        return filepath

    except requests.RequestException as e:
        logger.debug(f'[Poster] 下载失败 {poster_url}: {e}')
        return None
    except Exception as e:
        logger.debug(f'[Poster] 处理失败 {poster_url}: {e}')
        return None


def is_portrait(image_path):
    """检查本地图片是否为竖屏"""
    try:
        with Image.open(image_path) as img:
            w, h = img.size
            return h > w
    except Exception:
        return False
