"""海报下载器测试"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from io import BytesIO
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from anime_spider.utils.poster import download_poster, is_portrait


class TestPosterDownloader(unittest.TestCase):
    """海报下载器测试"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def _make_image_bytes(self, width, height, fmt='JPEG'):
        """创建测试图片字节"""
        img = Image.new('RGB', (width, height), color='red')
        buf = BytesIO()
        img.save(buf, format=fmt)
        return buf.getvalue()

    @patch('anime_spider.utils.poster.requests.get')
    def test_download_vertical_poster(self, mock_get):
        """竖屏海报应成功下载"""
        img_data = self._make_image_bytes(400, 600)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = img_data
        mock_resp.raise_for_status = MagicMock()
        mock_resp.headers = {'content-type': 'image/jpeg'}
        mock_get.return_value = mock_resp

        result = download_poster('https://example.com/poster.jpg', 'test_key', self.tmp_dir)
        self.assertIsNotNone(result)
        self.assertTrue(result.startswith('/posters/'))
        self.assertTrue(result.endswith('.jpg'))
        self.assertTrue(os.path.exists(os.path.join(self.tmp_dir, os.path.basename(result))))

    @patch('anime_spider.utils.poster.requests.get')
    def test_reject_horizontal_poster(self, mock_get):
        """横屏海报应被拒绝"""
        img_data = self._make_image_bytes(600, 400)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = img_data
        mock_resp.raise_for_status = MagicMock()
        mock_resp.headers = {'content-type': 'image/jpeg'}
        mock_get.return_value = mock_resp

        result = download_poster('https://example.com/poster.jpg', 'test_key', self.tmp_dir)
        self.assertIsNone(result)

    @patch('anime_spider.utils.poster.requests.get')
    def test_allow_horizontal_poster_when_portrait_not_required(self, mock_get):
        """关闭竖屏要求后，横屏图也应允许下载"""
        img_data = self._make_image_bytes(600, 400)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = img_data
        mock_resp.raise_for_status = MagicMock()
        mock_resp.headers = {'content-type': 'image/jpeg'}
        mock_get.return_value = mock_resp

        result = download_poster(
            'https://example.com/poster.jpg',
            'test_key',
            self.tmp_dir,
            require_portrait=False,
        )
        self.assertIsNotNone(result)
        self.assertTrue(result.startswith('/posters/'))

    @patch('anime_spider.utils.poster.requests.get')
    def test_reject_square_poster(self, mock_get):
        """正方形海报应被拒绝（非竖屏）"""
        img_data = self._make_image_bytes(400, 400)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = img_data
        mock_resp.raise_for_status = MagicMock()
        mock_resp.headers = {'content-type': 'image/jpeg'}
        mock_get.return_value = mock_resp

        result = download_poster('https://example.com/poster.jpg', 'test_key', self.tmp_dir)
        self.assertIsNone(result)

    @patch('anime_spider.utils.poster.requests.get')
    def test_reject_too_small(self, mock_get):
        """尺寸太小的图片应被拒绝"""
        img_data = self._make_image_bytes(100, 150)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = img_data
        mock_resp.raise_for_status = MagicMock()
        mock_resp.headers = {'content-type': 'image/jpeg'}
        mock_get.return_value = mock_resp

        result = download_poster('https://example.com/poster.jpg', 'test_key', self.tmp_dir)
        self.assertIsNone(result)

    @patch('anime_spider.utils.poster.requests.get')
    def test_download_failure(self, mock_get):
        """网络错误应返回 None"""
        mock_get.side_effect = Exception('Network error')
        result = download_poster('https://example.com/poster.jpg', 'test_key', self.tmp_dir)
        self.assertIsNone(result)

    def test_none_url(self):
        """URL 为 None 时返回 None"""
        result = download_poster(None, 'test_key', self.tmp_dir)
        self.assertIsNone(result)

    def test_none_key(self):
        """key 为 None 时返回 None"""
        result = download_poster('https://example.com/poster.jpg', None, self.tmp_dir)
        self.assertIsNone(result)

    @patch('anime_spider.utils.poster.requests.get')
    def test_different_formats(self, mock_get):
        """支持不同图片格式"""
        for fmt, ext in [('PNG', 'png'), ('JPEG', 'jpg')]:
            img_data = self._make_image_bytes(300, 500, fmt)
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.content = img_data
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            result = download_poster(f'https://example.com/poster.{ext}', f'key_{ext}', self.tmp_dir)
            self.assertIsNotNone(result)
            self.assertTrue(result.startswith('/posters/'))
            self.assertTrue(result.endswith(f'.{ext}'))

    def test_is_portrait_true(self):
        """竖屏图片检测"""
        path = os.path.join(self.tmp_dir, 'portrait.jpg')
        img = Image.new('RGB', (300, 500))
        img.save(path)
        self.assertTrue(is_portrait(path))

    def test_is_portrait_false(self):
        """横屏图片检测"""
        path = os.path.join(self.tmp_dir, 'landscape.jpg')
        img = Image.new('RGB', (500, 300))
        img.save(path)
        self.assertFalse(is_portrait(path))

    def test_is_portrait_nonexistent(self):
        """不存在的文件返回 False"""
        self.assertFalse(is_portrait('/nonexistent/file.jpg'))


if __name__ == '__main__':
    unittest.main()
