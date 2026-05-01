"""测试抓取统计计算。"""

import unittest

from anime_spider.utils.crawl_metrics import CrawlMetrics


class TestCrawlMetrics(unittest.TestCase):
    def test_build_domain_update_success(self):
        metrics = CrawlMetrics.build_domain_update(
            {},
            crawl_succeeded=True,
            quality_score=0.8,
            anime_count_delta=3,
        )
        self.assertEqual(metrics['total_crawls'], 1)
        self.assertEqual(metrics['success_crawls'], 1)
        self.assertEqual(metrics['total_anime_found'], 3)
        self.assertGreater(metrics['health_score'], 0)

    def test_build_domain_update_failure(self):
        metrics = CrawlMetrics.build_domain_update(
            {'total_crawls': 2, 'success_crawls': 1},
            crawl_succeeded=False,
        )
        self.assertEqual(metrics['total_crawls'], 3)
        self.assertEqual(metrics['success_crawls'], 1)
        self.assertLess(metrics['success_rate'], 1)


if __name__ == '__main__':
    unittest.main()
