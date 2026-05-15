"""增量巡检入口测试。"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run as backend_run


class FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def __iter__(self):
        return iter(self._docs)


class FakeCollection:
    def __init__(self, docs):
        self.docs = list(docs)
        self.find_calls = []

    def find(self, query, projection=None):
        self.find_calls.append((query, projection))
        return FakeCursor(self.docs)


class TestRunIncremental(unittest.TestCase):
    def test_select_incremental_candidates_keeps_only_top_limit(self):
        scheduler = MagicMock()
        scheduler.should_check.side_effect = lambda doc, min_hours=6: doc.get('allow', False)
        scheduler.score.side_effect = lambda doc: doc['score']

        docs = [
            {'title': 'A', 'score': 0.2, 'allow': True},
            {'title': 'B', 'score': 0.9, 'allow': True},
            {'title': 'C', 'score': 0.4, 'allow': False},
            {'title': 'D', 'score': 0.7, 'allow': True},
        ]

        selected = backend_run.select_incremental_candidates(docs, scheduler, limit=2, min_hours=6)

        self.assertEqual([doc['title'] for doc in selected], ['B', 'D'])

    def test_run_incremental_uses_projection_and_spawns_serial_crawls(self):
        docs = [
            {
                '_id': 'anime-1',
                'title': '番剧一',
                'source_urls': ['https://example.com/a1'],
            },
            {
                '_id': 'anime-2',
                'title': '番剧二',
                'source_urls': ['https://example.com/a2'],
            },
        ]
        fake_collection = FakeCollection(docs)
        fake_scheduler = MagicMock()
        fake_scheduler.should_check.return_value = True
        fake_scheduler.score.side_effect = [0.8, 0.7]
        fake_scheduler.build_targets.side_effect = [
            [{'url': 'https://example.com/a1', 'kind': 'detail'}],
            [{'url': 'https://example.com/a2', 'kind': 'detail'}],
        ]
        fake_result = MagicMock(returncode=0)

        with (
            patch('anime_spider.utils.db.MongoDB.get_anime_collection', return_value=fake_collection),
            patch('anime_spider.utils.db.MongoDB.close'),
            patch('anime_spider.utils.incremental_scheduler.IncrementalScheduler', return_value=fake_scheduler),
            patch('run.subprocess.run', return_value=fake_result) as mock_run,
        ):
            backend_run.run_incremental(limit=2, min_hours=6)

        self.assertEqual(fake_collection.find_calls[0][0], {'source_urls.0': {'$exists': True}})
        self.assertEqual(fake_collection.find_calls[0][1], backend_run.INCREMENTAL_CANDIDATE_PROJECTION)
        self.assertEqual(mock_run.call_count, 2)
        first_args = mock_run.call_args_list[0].args[0]
        self.assertEqual(first_args[:3], [sys.executable, backend_run.RUN_PY, 'crawl'])
        self.assertIn('https://example.com/a1', first_args)
        self.assertIn('--incremental-mode', first_args)

    def test_run_incremental_raises_when_child_crawl_fails(self):
        docs = [{'_id': 'anime-1', 'title': '番剧一', 'source_urls': ['https://example.com/a1']}]
        fake_collection = FakeCollection(docs)
        fake_scheduler = MagicMock()
        fake_scheduler.should_check.return_value = True
        fake_scheduler.score.return_value = 0.8
        fake_scheduler.build_targets.return_value = [{'url': 'https://example.com/a1', 'kind': 'detail'}]
        failed_result = MagicMock(returncode=137)

        with (
            patch('anime_spider.utils.db.MongoDB.get_anime_collection', return_value=fake_collection),
            patch('anime_spider.utils.db.MongoDB.close'),
            patch('anime_spider.utils.incremental_scheduler.IncrementalScheduler', return_value=fake_scheduler),
            patch('run.subprocess.run', return_value=failed_result),
        ):
            with self.assertRaises(RuntimeError):
                backend_run.run_incremental(limit=1, min_hours=6)


if __name__ == '__main__':
    unittest.main()
