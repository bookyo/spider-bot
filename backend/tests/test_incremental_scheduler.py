"""测试增量巡检调度器。"""

import unittest
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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

    def test_build_targets_skips_douban_subject_urls(self):
        doc = {
            'source_urls': [
                'https://movie.douban.com/subject/35027714/',
                'https://example.com/anime/123',
            ],
            'source_domain': 'example.com',
            'latest_episode': '12',
            'total_episode_count': 12,
        }

        targets = self.scheduler.build_targets(doc)

        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]['url'], 'https://example.com/anime/123')


if __name__ == '__main__':
    unittest.main()
