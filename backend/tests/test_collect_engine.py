"""资源站采集引擎单测。"""

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pymongo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.collect_engine import CollectEngine, merge_play_sources


class FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    async def to_list(self, _limit):
        return list(self._docs)


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.update_calls = []
        self.insert_calls = []

    def find(self, query):
        if 'url_hash' in query:
            url_hashes = set(query['url_hash'].get('$in', []))
            docs = [doc for doc in self.docs if doc.get('url_hash') in url_hashes]
            return FakeCursor(docs)
        docs = [doc for doc in self.docs if _matches_query(doc, query)]
        return FakeCursor(docs)

    async def update_one(self, query, update, upsert=False):
        self.update_calls.append({
            'query': query,
            'update': update,
            'upsert': upsert,
        })
        for doc in self.docs:
            if _matches_query(doc, query):
                doc.update(update.get('$set', {}))
                break

    async def insert_one(self, doc):
        dedup_key = doc.get('dedup_key')
        if dedup_key and any(existing.get('dedup_key') == dedup_key for existing in self.docs):
            raise pymongo.errors.DuplicateKeyError('duplicate dedup_key')
        self.docs.append(dict(doc))
        self.insert_calls.append(doc)
        return type('InsertResult', (), {'inserted_id': doc.get('_id')})()


def _matches_query(doc, query):
    if not query:
        return True
    if '$or' in query:
        return any(_matches_query(doc, sub_query) for sub_query in query['$or'])

    for key, expected in query.items():
        actual = doc.get(key)
        if isinstance(expected, dict):
            if '$in' in expected:
                values = expected['$in']
                if isinstance(actual, list):
                    if not any(value in actual for value in values):
                        return False
                elif actual not in values:
                    return False
                continue
        if actual != expected:
            return False
    return True


class FakeDB:
    def __init__(self, collections):
        self._collections = collections

    def __getitem__(self, name):
        return self._collections[name]


class TestCollectEngine(unittest.IsolatedAsyncioTestCase):
    async def test_run_updates_existing_item_even_when_bind_disabled(self):
        engine = CollectEngine()
        source = {
            '_id': 'source-1',
            'name': '360zy',
            'url': 'https://360zy.com/api.php/provide/vod',
            'type': 'json',
            'bind': False,
            'collect_num': 0,
        }
        existing_anime = {
            '_id': 'anime-1',
            'title': '测试动画',
            'play_sources': [{
                'source_name': 'ffm3u8',
                'domain': '360zy.com',
                'episodes': [{'episode': '1', 'url': 'https://old.example/1.m3u8'}],
            }],
            'source_urls': ['https://360zy.com/api.php/provide/vod?ac=detail&ids=123'],
            'genres': ['动画'],
            'aliases': [],
            'dedup_key': 'dedup-1',
        }
        history_collection = FakeCollection([{
            'url_hash': 'hash-1',
            'source_time': '2026-05-16 10:00:00',
        }])
        anime_collection = FakeCollection()
        collect_sources = FakeCollection()
        fake_db = FakeDB({
            'collect_history': history_collection,
            'anime': anime_collection,
            'collect_sources': collect_sources,
            'collect_type_bindings': FakeCollection(),
        })

        normalized = {
            'title': '测试动画',
            'play_sources': [{
                'source_name': 'ffm3u8',
                'domain': '360zy.com',
                'episodes': [{'episode': '1', 'url': 'https://new.example/1.m3u8'}],
            }],
            'source_urls': ['https://360zy.com/api.php/provide/vod?ac=detail&ids=123'],
            'genres': ['动画'],
            'aliases': [],
            'dedup_key': 'dedup-1',
        }

        with (
            patch('services.collect_engine.get_db', return_value=fake_db),
            patch.object(engine, 'fetch_list', AsyncMock(return_value={
                'list': [{
                    'vod_id': '123',
                    'vod_name': '测试动画',
                    'vod_time': '2026-05-17 10:00:00',
                    'vod_play_url': '1$https://new.example/1.m3u8',
                    'vod_play_from': 'ffm3u8',
                }],
                'pagecount': 1,
            })),
            patch.object(engine, 'find_existing_anime_map', AsyncMock(return_value={})),
            patch.object(engine, 'resolve_existing', return_value=existing_anime),
            patch.object(engine, 'normalize', return_value=normalized),
            patch('services.collect_engine.build_collect_url_hash', return_value='hash-1'),
            patch('services.collect_engine.download_poster_with_retry', AsyncMock(return_value='/posters/no-poster.png')),
        ):
            result = await engine.run(source=source, range_type='today')

        self.assertEqual(result['updated'], 1)
        self.assertEqual(result['skipped'], 0)
        self.assertEqual(len(anime_collection.update_calls), 1)
        merged = anime_collection.update_calls[0]['update']['$set']
        self.assertEqual(
            merged['play_sources'][0]['episodes'][0]['url'],
            'https://new.example/1.m3u8',
        )

    async def test_resolve_existing_matches_by_dedup_key(self):
        engine = CollectEngine()
        existing_anime = {
            '_id': 'anime-1',
            'title': '旧标题',
            'year': None,
            'genres': ['动画'],
            'dedup_key': 'same-dedup',
            'aliases': [],
            'play_sources': [],
        }
        fake_db = FakeDB({
            'anime': FakeCollection([existing_anime]),
        })
        incoming = {
            'title': '新标题',
            'year': 2024,
            'genres': ['动画'],
            'dedup_key': 'same-dedup',
            'aliases': [],
        }

        with patch('services.collect_engine.get_db', return_value=fake_db):
            lookup = await engine.find_existing_anime_map([incoming])

        resolved = engine.resolve_existing(incoming, lookup)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved['_id'], 'anime-1')

    async def test_run_merges_duplicate_dedup_key_within_same_batch(self):
        engine = CollectEngine()
        source = {
            '_id': 'source-3',
            'name': '魔都',
            'url': 'https://example.com/api.php/provide/vod',
            'type': 'json',
            'bind': False,
            'collect_num': 0,
        }
        anime_collection = FakeCollection()
        fake_db = FakeDB({
            'collect_history': FakeCollection(),
            'anime': anime_collection,
            'collect_sources': FakeCollection(),
            'collect_type_bindings': FakeCollection(),
        })

        same_dedup = 'same-dedup'
        normalized_docs = [
            {
                'title': '测试动画',
                'year': 2024,
                'genres': ['动画'],
                'aliases': [],
                'source_urls': ['https://detail.example/1'],
                'play_sources': [{
                    'source_name': 'm3u8',
                    'domain': 'example.com',
                    'episodes': [{'episode': '1', 'url': 'https://cdn.example/1.m3u8'}],
                }],
                'dedup_key': same_dedup,
            },
            {
                'title': '测试动画',
                'year': 2024,
                'genres': ['动画'],
                'aliases': [],
                'source_urls': ['https://detail.example/2'],
                'play_sources': [{
                    'source_name': 'm3u8',
                    'domain': 'example.com',
                    'episodes': [{'episode': '2', 'url': 'https://cdn.example/2.m3u8'}],
                }],
                'dedup_key': same_dedup,
            },
        ]

        with (
            patch('services.collect_engine.get_db', return_value=fake_db),
            patch.object(engine, 'fetch_list', AsyncMock(return_value={
                'list': [
                    {
                        'vod_id': '1',
                        'vod_name': '测试动画',
                        'vod_play_url': '1$https://cdn.example/1.m3u8',
                        'vod_play_from': 'm3u8',
                    },
                    {
                        'vod_id': '2',
                        'vod_name': '测试动画',
                        'vod_play_url': '2$https://cdn.example/2.m3u8',
                        'vod_play_from': 'm3u8',
                    },
                ],
                'pagecount': 1,
            })),
            patch.object(engine, 'normalize', side_effect=normalized_docs),
            patch('services.collect_engine.build_collect_url_hash', side_effect=['hash-1', 'hash-2']),
            patch('services.collect_engine.download_poster_with_retry', AsyncMock(return_value='/posters/no-poster.png')),
        ):
            result = await engine.run(source=source, range_type='today')

        self.assertEqual(result['created'], 1)
        self.assertEqual(result['updated'], 1)
        self.assertEqual(len(anime_collection.insert_calls), 1)
        self.assertEqual(len(anime_collection.update_calls), 1)

    async def test_run_filters_by_selected_remote_types_and_fills_local_type(self):
        engine = CollectEngine()
        source = {
            '_id': 'source-2',
            'name': 'ffzy',
            'url': 'http://api.ffzyapi.com/api.php/provide/vod/from/ffm3u8/at/xml/',
            'type': 'xml',
            'bind': False,
            'collect_num': 0,
        }
        anime_collection = FakeCollection()
        fake_db = FakeDB({
            'collect_history': FakeCollection(),
            'anime': anime_collection,
            'collect_sources': FakeCollection(),
            'collect_type_bindings': FakeCollection([{
                'collect_source': 'source-2',
                'source_type_id': '20',
                'source_type_name': '剧场版',
                'local_type': '剧场版',
            }]),
        })

        def normalize_side_effect(item, _source):
            return {
                'title': item['vod_name'],
                'genres': [item.get('type_name', '')],
                'aliases': [],
                'source_urls': [f"https://detail.example/{item['vod_id']}"],
                'play_sources': [{
                    'source_name': 'ffm3u8',
                    'domain': 'api.ffzyapi.com',
                    'episodes': [{'episode': '1', 'url': f"https://cdn.example/{item['vod_id']}.m3u8"}],
                }],
                'dedup_key': item['vod_id'],
            }

        with (
            patch('services.collect_engine.get_db', return_value=fake_db),
            patch.object(engine, 'fetch_list', AsyncMock(return_value={
                'list': [
                    {
                        'vod_id': 'keep-1',
                        'vod_name': '保留条目',
                        'type_id': '20',
                        'type_name': '剧场版',
                        'vod_play_url': '1$https://cdn.example/keep.m3u8',
                        'vod_play_from': 'ffm3u8',
                    },
                    {
                        'vod_id': 'skip-1',
                        'vod_name': '跳过条目',
                        'type_id': '99',
                        'type_name': '综艺',
                        'vod_play_url': '1$https://cdn.example/skip.m3u8',
                        'vod_play_from': 'ffm3u8',
                    },
                ],
                'pagecount': 1,
            })),
            patch.object(engine, 'find_existing_anime_map', AsyncMock(return_value={})),
            patch.object(engine, 'resolve_existing', return_value=None),
            patch.object(engine, 'normalize', side_effect=normalize_side_effect),
            patch('services.collect_engine.download_poster_with_retry', AsyncMock(return_value='/posters/no-poster.png')),
        ):
            result = await engine.run(source=source, range_type='today')

        self.assertEqual(result['created'], 1)
        self.assertEqual(result['skipped'], 1)
        self.assertEqual(len(anime_collection.insert_calls), 1)
        inserted = anime_collection.insert_calls[0]
        self.assertEqual(inserted['title'], '保留条目')
        self.assertIn('剧场版', inserted['genres'])

    def test_merge_play_sources_replaces_stale_episode_url(self):
        merged = merge_play_sources(
            [{
                'source_name': 'ffm3u8',
                'domain': 'api.ffzyapi.com',
                'episodes': [{'episode': '1', 'url': 'https://old.example/1.m3u8'}],
            }],
            [{
                'source_name': 'ffm3u8',
                'domain': 'api.ffzyapi.com',
                'episodes': [{'episode': '1', 'url': 'https://new.example/1.m3u8'}],
            }],
        )

        self.assertEqual(len(merged), 1)
        self.assertEqual(len(merged[0]['episodes']), 1)
        self.assertEqual(merged[0]['episodes'][0]['url'], 'https://new.example/1.m3u8')
        self.assertEqual(merged[0]['episodes'][0]['previous_url'], 'https://old.example/1.m3u8')

    def test_parse_xml_video_keeps_multiple_dd_lines(self):
        engine = CollectEngine()
        xml_text = """
<rss version="2.0">
  <list page="1" pagecount="1" recordcount="1">
    <video>
      <id>100</id>
      <name><![CDATA[测试动画]]></name>
      <tid>1</tid>
      <type><![CDATA[动画]]></type>
      <last>2026-05-17 10:00:00</last>
      <dl>
        <dd flag="ffm3u8"><![CDATA[第1集$https://cdn-a.example/1.m3u8]]></dd>
        <dd flag="lzm3u8"><![CDATA[第1集$https://cdn-b.example/1.m3u8]]></dd>
      </dl>
    </video>
  </list>
</rss>
"""

        parsed = engine._parse_xml_list(xml_text, 1)
        self.assertEqual(len(parsed['list']), 1)
        item = parsed['list'][0]
        self.assertEqual(item['vod_play_from'], 'ffm3u8$$$lzm3u8')
        self.assertEqual(
            item['vod_play_url'],
            '第1集$https://cdn-a.example/1.m3u8$$$第1集$https://cdn-b.example/1.m3u8',
        )


if __name__ == '__main__':
    unittest.main()
