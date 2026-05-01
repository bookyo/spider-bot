"""测试站型指纹识别。"""

import unittest
from unittest.mock import MagicMock

from anime_spider.utils.site_fingerprint import SiteFingerprint


class TestSiteFingerprint(unittest.TestCase):
    """测试站型识别器。"""

    def setUp(self):
        self.fingerprint = SiteFingerprint()

    def _mock_response(self, text):
        response = MagicMock()
        response.text = text
        return response

    def test_detect_maccms(self):
        response = self._mock_response('<div class="stui-vodlist"></div><div class="stui-content__playlist"></div>')
        result = self.fingerprint.detect(response)
        self.assertEqual(result['site_type'], 'maccms')
        self.assertGreater(result['confidence'], 0)

    def test_detect_generic_when_unknown(self):
        response = self._mock_response('<html><body>plain page</body></html>')
        result = self.fingerprint.detect(response)
        self.assertEqual(result['site_type'], 'generic')


if __name__ == '__main__':
    unittest.main()
