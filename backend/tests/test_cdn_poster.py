"""CDN 海报上传测试。"""

import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from anime_spider.utils.poster import download_poster
from services.collect_engine import download_poster_with_retry


def _make_image_bytes(width=400, height=600, fmt='JPEG'):
    image = Image.new('RGB', (width, height), color='blue')
    buffer = BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


class TestCdnPosterUpload(unittest.IsolatedAsyncioTestCase):
    @patch.dict(
        'os.environ',
        {
            'CDN_UPLOAD_BASE_URL': 'https://cdn.example.com',
            'CDN_UPLOAD_API_KEY': 'key',
            'CDN_UPLOAD_API_SECRET': 'secret',
        },
        clear=False,
    )
    @patch('anime_spider.utils.poster.requests.post')
    @patch('anime_spider.utils.poster.requests.get')
    def test_download_poster_uploads_to_cdn(self, mock_get, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = _make_image_bytes()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.headers = {'content-type': 'image/jpeg'}
        mock_get.return_value = mock_resp

        signed_resp = MagicMock()
        signed_resp.raise_for_status = MagicMock()
        signed_resp.json.return_value = {'uploadUrl': '/api/upload/file'}

        upload_resp = MagicMock()
        upload_resp.raise_for_status = MagicMock()
        upload_resp.json.return_value = {
            'publicUrl': 'https://cdn.example.com/api/processed/public/file/test.jpg',
        }
        mock_post.side_effect = [signed_resp, upload_resp]

        result = download_poster('https://img.example.com/poster.jpg', 'dedup-key')

        self.assertEqual(
            result,
            'https://cdn.example.com/api/processed/public/file/test.jpg',
        )
        self.assertEqual(mock_post.call_count, 2)

    @patch.dict(
        'os.environ',
        {
            'CDN_UPLOAD_BASE_URL': 'https://cdn.example.com',
            'CDN_UPLOAD_API_KEY': 'key',
            'CDN_UPLOAD_API_SECRET': 'secret',
        },
        clear=False,
    )
    @patch('services.collect_engine.upload_poster_to_cdn', new_callable=AsyncMock)
    @patch('services.collect_engine.httpx.AsyncClient')
    async def test_collect_engine_download_poster_uploads_to_cdn(self, mock_client_cls, mock_upload):
        mock_upload.return_value = 'https://cdn.example.com/api/processed/public/file/collect.jpg'

        mock_response = MagicMock()
        mock_response.content = _make_image_bytes()
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client_cls.return_value.__aexit__.return_value = False

        result = await download_poster_with_retry(
            'https://img.example.com/collect.jpg',
            'dedup-key',
        )

        self.assertEqual(
            result,
            'https://cdn.example.com/api/processed/public/file/collect.jpg',
        )
        mock_upload.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
