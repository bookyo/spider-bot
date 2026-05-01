"""测试增量巡检调度器。"""

import unittest
from datetime import datetime, timedelta, timezone

from anime_spider.utils.incremental_scheduler import IncrementalScheduler


class TestIncrementalScheduler(unittest.TestCase):
    def setUp(self):
        self.scheduler = IncrementalScheduler()

    def test_should_check_when_missing_timestamp(self):
        self.assertTrue(self.scheduler.should_check({}))

    def test_should_check_false_when_recent(self):
        doc = {
            'last_incremental_check': datetime.now(timezone.utc) - timedelta(hours=1),
        }
        self.assertFalse(self.scheduler.should_check(doc, min_hours=6))

    def test_score_prefers_incremental_and_stale(self):
        stale = {
            'incremental_found': True,
            'quality_score': 0.8,
            'total_episode_count': 12,
            'latest_episode': '12',
            'last_incremental_check': datetime.now(timezone.utc) - timedelta(hours=48),
        }
        fresh = {
            'incremental_found': False,
            'quality_score': 0.8,
            'total_episode_count': 12,
            'latest_episode': '12',
            'last_incremental_check': datetime.now(timezone.utc) - timedelta(hours=1),
        }
        self.assertGreater(self.scheduler.score(stale), self.scheduler.score(fresh))


if __name__ == '__main__':
    unittest.main()
