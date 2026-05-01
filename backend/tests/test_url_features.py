"""测试 URL 特征分析。"""

import unittest

from anime_spider.utils.url_features import URLFeatureAnalyzer


class TestURLFeatureAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = URLFeatureAnalyzer()

    def test_detail_url(self):
        result = self.analyzer.analyze('https://example.com/vod/123')
        self.assertEqual(result['page_type'], 'detail')
        self.assertGreater(result['score'], 0)

    def test_list_url(self):
        result = self.analyzer.analyze('https://example.com/type/action')
        self.assertEqual(result['page_type'], 'list')

    def test_unknown_url(self):
        result = self.analyzer.analyze('https://example.com/about')
        self.assertEqual(result['page_type'], 'unknown')


if __name__ == '__main__':
    unittest.main()
