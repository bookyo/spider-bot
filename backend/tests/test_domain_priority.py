"""测试域名优先级评分。"""

import unittest
from datetime import datetime, timedelta, timezone

from anime_spider.utils.domain_priority import DomainPriorityScorer


class TestDomainPriorityScorer(unittest.TestCase):
    def setUp(self):
        self.scorer = DomainPriorityScorer()

    def test_pending_domain_scores_higher(self):
        now = datetime.now(timezone.utc) - timedelta(days=10)
        pending = self.scorer.score({
            'is_anime_site': True,
            'status': 'pending',
            'last_crawled': now,
        })
        failed = self.scorer.score({
            'is_anime_site': True,
            'status': 'failed',
            'last_crawled': now,
        })
        self.assertGreater(pending, failed)

    def test_retry_penalty(self):
        base = self.scorer.score({'is_anime_site': True, 'status': 'pending'})
        penalized = self.scorer.score({'is_anime_site': True, 'status': 'pending', 'retry_count': 3})
        self.assertLess(penalized, base)


if __name__ == '__main__':
    unittest.main()
