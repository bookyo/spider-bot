"""采集任务队列运行器测试。"""

import sys
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.collect_task_runner import CollectTaskRunner, _now


class FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    async def to_list(self, _limit):
        return list(self._docs)


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.update_calls = []

    def find(self, query):
        docs = [doc for doc in self.docs if _matches_query(doc, query)]
        return FakeCursor(docs)

    async def update_one(self, query, update):
        self.update_calls.append({'query': query, 'update': update})
        for doc in self.docs:
            if _matches_query(doc, query):
                if '$set' in update:
                    doc.update(update['$set'])
                break

    async def update_many(self, query, update):
        for doc in self.docs:
            if _matches_query(doc, query):
                if '$set' in update:
                    doc.update(update['$set'])

    async def find_one(self, query):
        for doc in self.docs:
            if _matches_query(doc, query):
                return dict(doc)
        return None


class FakeDB:
    def __init__(self, collections):
        self._collections = collections

    def __getitem__(self, name):
        return self._collections[name]


def _matches_query(doc, query):
    if not query:
        return True
    for key, expected in query.items():
        actual = doc.get(key)
        if isinstance(expected, dict) and '$in' in expected:
            if actual not in expected['$in']:
                return False
            continue
        if key == '_id':
            if str(actual) != str(expected):
                return False
            continue
        if actual != expected:
            return False
    return True


class TestCollectTaskRunner(unittest.IsolatedAsyncioTestCase):
    async def test_fail_stale_tasks_resets_active_worker_and_refreshes_queue(self):
        now = _now()
        stale_time = now - timedelta(minutes=11)
        running_id = '682d2a0f0000000000000001'
        pending_id = '682d2a0f0000000000000002'
        task_collection = FakeCollection([
            {
                '_id': running_id,
                'status': 'running',
                'heartbeat_at': stale_time,
                'source_name': '360资源',
            },
            {
                '_id': pending_id,
                'status': 'pending',
                'heartbeat_at': now,
                'source_name': '电影天堂',
            },
        ])
        db = FakeDB({'collect_tasks': task_collection})
        runner = CollectTaskRunner()
        runner.running = True
        runner.active_task_id = running_id
        runner.active_source_name = '360资源'
        runner.queue = [pending_id]

        with patch('services.collect_task_runner.get_db', return_value=db):
            failed = await runner._fail_stale_tasks()

        self.assertEqual(failed, 1)
        self.assertFalse(runner.running)
        self.assertIsNone(runner.active_task_id)
        self.assertEqual(runner.active_source_name, '')
        self.assertEqual(runner.queue, [pending_id])
        failed_doc = task_collection.docs[0]
        self.assertEqual(failed_doc['status'], 'failed')
        self.assertIn('任务心跳超时', failed_doc['message'])
        pending_doc = task_collection.docs[1]
        self.assertEqual(pending_doc['queue_position'], 1)

    async def test_recover_stale_tasks_clears_memory_queue(self):
        now = _now()
        task_collection = FakeCollection([
            {
                '_id': '682d2a0f0000000000000011',
                'status': 'pending',
                'heartbeat_at': now,
            },
            {
                '_id': '682d2a0f0000000000000012',
                'status': 'running',
                'heartbeat_at': now,
            },
        ])
        db = FakeDB({'collect_tasks': task_collection})
        runner = CollectTaskRunner()
        runner.running = True
        runner.active_task_id = '682d2a0f0000000000000012'
        runner.active_source_name = '无尽'
        runner.queue = ['682d2a0f0000000000000011']

        with patch('services.collect_task_runner.get_db', return_value=db):
            await runner.recover_stale_tasks()

        self.assertFalse(runner.running)
        self.assertIsNone(runner.active_task_id)
        self.assertEqual(runner.active_source_name, '')
        self.assertEqual(runner.queue, [])
        self.assertTrue(all(doc['status'] == 'failed' for doc in task_collection.docs))
