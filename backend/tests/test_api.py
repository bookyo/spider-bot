"""API 接口测试 - 需要 MongoDB 运行"""

import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.app import app
import api.database


class TestAPI(unittest.IsolatedAsyncioTestCase):
    """API 集成测试"""

    async def asyncSetUp(self):
        self.motor_client = AsyncIOMotorClient('mongodb://localhost:27017')
        self.db = self.motor_client['anime_db_test_api']

        # 注入测试数据库
        api.database.db = self.db

        # 清空数据
        await self.db['anime'].delete_many({})
        await self.db['discovered_domains'].delete_many({})
        await self.db['collect_sources'].delete_many({})

        # 插入测试数据
        self.anime_id = ObjectId()
        await self.db['anime'].insert_one({
            '_id': self.anime_id,
            'title': '鬼灭之刃',
            'original_title': '鬼滅の刃',
            'year': 2019,
            'director': '外崎春雄',
            'voice_actors': ['花江夏树', '鬼头明里'],
            'synopsis': '卖炭少年炭治郎的冒险故事',
            'poster_url': 'https://example.com/poster.jpg',
            'source_urls': ['https://example.com/anime/123'],
            'source_domain': 'example.com',
            'genres': ['动作', '奇幻'],
            'dedup_key': 'test_key_1',
            'play_sources': [
                {
                    'domain': 'player.example.com',
                    'episodes': [
                        {'episode': '01', 'url': 'https://p.com/01.m3u8'},
                        {'episode': '02', 'url': 'https://p.com/02.m3u8'},
                    ],
                    'quality': '1080p',
                    'raw_url': 'https://example.com/play/123',
                }
            ],
            'discovered_at': datetime.now(),
            'updated_at': datetime.now(),
        })

        await self.db['anime'].insert_one({
            '_id': ObjectId(),
            'title': '进击的巨人',
            'year': 2013,
            'director': '的場雅幸',
            'voice_actors': ['梶裕贵', '石川由依'],
            'genres': ['动作', '奇幻', '热血'],
            'dedup_key': 'test_key_2',
            'play_sources': [],
            'discovered_at': datetime.now(),
            'updated_at': datetime.now(),
        })

        await self.db['discovered_domains'].insert_one({
            'domain': 'anime-test.com',
            'source': 'crt_sh',
            'is_anime_site': True,
            'status': 'completed',
            'discovered_at': datetime.now(),
        })

        await self.db['discovered_domains'].insert_one({
            'domain': 'pending-site.com',
            'source': 'dns_enum',
            'is_anime_site': True,
            'status': 'pending',
            'discovered_at': datetime.now(),
        })

        transport = ASGITransport(app=app)
        self.ac = AsyncClient(transport=transport, base_url='http://test')
        self.admin_api_key = 'test-admin-key'
        self._old_admin_api_key = os.environ.get('ADMIN_API_KEY')
        os.environ['ADMIN_API_KEY'] = self.admin_api_key

    async def asyncTearDown(self):
        await self.ac.aclose()
        self.motor_client.close()
        if self._old_admin_api_key is None:
            os.environ.pop('ADMIN_API_KEY', None)
        else:
            os.environ['ADMIN_API_KEY'] = self._old_admin_api_key

    # --- 动画列表测试 ---

    async def test_list_anime_default(self):
        resp = await self.ac.get('/api/anime')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['data']), 2)
        self.assertEqual(data['meta']['total'], 2)

    async def test_list_anime_pagination(self):
        resp = await self.ac.get('/api/anime?page=1&page_size=1')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['data']), 1)
        self.assertEqual(data['meta']['total_pages'], 2)

    async def test_list_anime_keyword_search(self):
        resp = await self.ac.get('/api/anime?keyword=鬼灭')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['data']), 1)
        self.assertEqual(data['data'][0]['title'], '鬼灭之刃')

    async def test_list_anime_year_filter(self):
        resp = await self.ac.get('/api/anime?year=2019')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['data']), 1)
        self.assertEqual(data['data'][0]['year'], 2019)

    async def test_list_anime_genre_filter(self):
        resp = await self.ac.get('/api/anime?genre=热血')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['data']), 1)
        self.assertEqual(data['data'][0]['title'], '进击的巨人')

    async def test_list_anime_sort_by_year(self):
        resp = await self.ac.get('/api/anime?sort_by=year&sort_order=asc')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['data'][0]['year'], 2013)

    async def test_list_anime_empty_result(self):
        resp = await self.ac.get('/api/anime?keyword=不存在的动画')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['data']), 0)
        self.assertEqual(data['meta']['total'], 0)

    # --- 动画详情测试 ---

    async def test_get_anime_detail(self):
        resp = await self.ac.get(f'/api/anime/{self.anime_id}')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['title'], '鬼灭之刃')
        self.assertEqual(data['year'], 2019)
        self.assertEqual(data['director'], '外崎春雄')
        self.assertEqual(len(data['voice_actors']), 2)
        self.assertEqual(len(data['play_sources']), 1)
        self.assertEqual(len(data['play_sources'][0]['episodes']), 2)

    async def test_get_anime_detail_not_found(self):
        fake_id = str(ObjectId())
        resp = await self.ac.get(f'/api/anime/{fake_id}')
        self.assertEqual(resp.status_code, 404)

    async def test_get_anime_detail_invalid_id(self):
        resp = await self.ac.get('/api/anime/invalid_id')
        self.assertEqual(resp.status_code, 400)

    # --- 播放源测试 ---

    async def test_get_anime_sources(self):
        resp = await self.ac.get(f'/api/anime/{self.anime_id}/sources')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['domain'], 'player.example.com')
        self.assertEqual(len(data[0]['episodes']), 2)

    # --- 域名列表测试 ---

    async def test_list_domains(self):
        resp = await self.ac.get('/api/domains')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['data']), 2)

    async def test_list_domains_status_filter(self):
        resp = await self.ac.get('/api/domains?status=pending')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['data']), 1)
        self.assertEqual(data['data'][0]['domain'], 'pending-site.com')

    async def test_get_domain_detail(self):
        resp = await self.ac.get('/api/domains/anime-test.com')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['domain'], 'anime-test.com')
        self.assertTrue(data['is_anime_site'])

    async def test_get_domain_not_found(self):
        resp = await self.ac.get('/api/domains/not-exist.com')
        self.assertEqual(resp.status_code, 404)

    # --- 统计测试 ---

    async def test_get_stats(self):
        resp = await self.ac.get('/api/stats')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['total_anime'], 2)
        self.assertEqual(data['total_domains'], 2)
        self.assertEqual(data['anime_sites'], 2)
        self.assertEqual(data['pending_domains'], 1)
        self.assertIn('year_distribution', data)
        self.assertIn('top_genres', data)

    # --- 根路径测试 ---

    async def test_root(self):
        resp = await self.ac.get('/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['name'], '动漫爬虫 API')

    async def test_admin_collect_source_test_uses_collect_engine_fetch_list(self):
        source_id = ObjectId()
        await self.db['collect_sources'].insert_one({
            '_id': source_id,
            'name': '非凡',
            'url': 'http://api.ffzyapi.com/api.php/provide/vod/from/ffm3u8/at/xml/',
            'type': 'xml',
            'mid': 1,
            'appid': '',
            'appkey': '',
            'bind': False,
            'status': True,
            'filter': {'area': '', 'year': '', 'class': '', 'type': []},
            'last_collect': None,
            'collect_num': 0,
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
        })

        with patch(
            'api.routes.collect.collect_engine.fetch_list',
            AsyncMock(return_value={
                'list': [{'vod_id': '1', 'vod_name': '测试条目'}],
                'types': [{'type_id': '30', 'type_name': '日韩动漫'}],
                'page': 1,
                'pagecount': 1,
                'total': 1,
            }),
        ) as mock_fetch_list:
            resp = await self.ac.post(
                f'/api/admin/collect/sources/{source_id}/test',
                headers={'x-api-key': self.admin_api_key},
            )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['message'], '连接成功')
        self.assertIn('测试条目', data['preview'])
        mock_fetch_list.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
