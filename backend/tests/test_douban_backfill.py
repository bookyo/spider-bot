"""豆瓣回填任务测试。"""

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api import scheduler


class FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def __aiter__(self):
        self._iter = iter(self._docs)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class FakeAnimeCollection:
    def __init__(self, docs):
        self.docs = list(docs)
        self.updates = []

    def find(self, *args, **kwargs):
        return FakeCursor(self.docs)

    async def update_one(self, query, update):
        self.updates.append((query, update))


class FakeDB:
    def __init__(self, anime_docs):
        self.anime = FakeAnimeCollection(anime_docs)

    def __getitem__(self, name):
        if name == 'anime':
            return self.anime
        raise KeyError(name)


class TestDoubanBackfill(unittest.IsolatedAsyncioTestCase):
    async def test_assigns_no_poster_placeholder_when_search_has_no_match(self):
        doc = {
            '_id': 'anime-1',
            'title': '没有如果',
            'year': 2025,
            'poster_local': None,
            'source_urls': [],
        }
        fake_db = FakeDB([doc])

        with (
            patch.object(scheduler, 'get_db', return_value=fake_db),
            patch.object(scheduler, 'get_admin_settings', AsyncMock(return_value={
                'douban_backfill_limit': 50,
                'douban_search_url': 'https://s.stdlang.com/search',
                'douban_backfill_timeout_seconds': 20,
                'crawler_proxy_url': None,
            })),
            patch.object(scheduler, '_update_backfill_status', AsyncMock()),
            patch.object(scheduler, '_update_douban_backfill_output', AsyncMock()),
            patch.object(scheduler, 'search_douban_subject_url', return_value=None),
        ):
            result = await scheduler.run_douban_backfill_job(force=True)

        self.assertEqual(result['updated'], 1)
        self.assertEqual(result['matched'], 0)
        self.assertEqual(result['failed'], 0)
        self.assertEqual(len(fake_db.anime.updates), 1)
        _, update = fake_db.anime.updates[0]
        self.assertEqual(update['$set']['poster_local'], 'posters/no-poster.png')

    async def test_does_not_append_douban_subject_url_to_source_urls(self):
        doc = {
            '_id': 'anime-2',
            'title': '爱没有距离',
            'year': 2025,
            'poster_local': '/posters/existing.jpg',
            'poster_url': None,
            'source_urls': ['https://example.com/anime/456'],
            'director': None,
            'synopsis': None,
            'voice_actors': [],
            'genres': [],
            'douban_rating': None,
            'imdb_rating': None,
        }
        fake_db = FakeDB([doc])
        subject_url = 'https://movie.douban.com/subject/35027714/'
        metadata = {
            'director': '测试导演',
            'synopsis': '测试简介',
        }

        with (
            patch.object(scheduler, 'get_db', return_value=fake_db),
            patch.object(scheduler, 'get_admin_settings', AsyncMock(return_value={
                'douban_backfill_limit': 50,
                'douban_search_url': 'https://s.stdlang.com/search',
                'douban_backfill_timeout_seconds': 20,
                'crawler_proxy_url': None,
            })),
            patch.object(scheduler, '_update_backfill_status', AsyncMock()),
            patch.object(scheduler, '_update_douban_backfill_output', AsyncMock()),
            patch.object(scheduler, 'search_douban_subject_url', return_value={'url': subject_url}),
            patch.object(scheduler, 'fetch_douban_subject_metadata', return_value={
                'metadata': metadata,
                'blocked': False,
                'status_code': 200,
                'url': subject_url,
            }),
        ):
            result = await scheduler.run_douban_backfill_job(force=True)

        self.assertEqual(result['updated'], 1)
        self.assertEqual(len(fake_db.anime.updates), 1)
        _, update = fake_db.anime.updates[0]
        self.assertNotIn('source_urls', update['$set'])


if __name__ == '__main__':
    unittest.main()
