"""端到端测试: 模拟爬取 → Pipeline入库 → API查询 的完整流程

测试流程:
1. 模拟爬虫产出 AnimeItem / DomainItem
2. 通过 Pipeline 写入 MongoDB
3. 通过 API 查询验证数据一致性
4. 验证去重、播放源合并、搜索筛选
"""

import unittest
from datetime import datetime
from unittest.mock import MagicMock
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from httpx import AsyncClient, ASGITransport

from anime_spider.items import AnimeItem, DomainItem
from anime_spider.pipelines import AnimePipeline
from api.app import app
import api.database


class TestEndToEnd(unittest.IsolatedAsyncioTestCase):
    """端到端集成测试"""

    DB_NAME = 'anime_db_e2e_test'

    @classmethod
    def setUpClass(cls):
        cls.sync_client = MongoClient('mongodb://localhost:27017')
        cls.sync_db = cls.sync_client[cls.DB_NAME]

    @classmethod
    def tearDownClass(cls):
        cls.sync_client.drop_database(cls.DB_NAME)
        cls.sync_client.close()

    async def asyncSetUp(self):
        # 清理
        self.sync_db.drop_collection('anime')
        self.sync_db.drop_collection('discovered_domains')

        # 初始化 Motor 客户端（给 API 用）
        self.motor_client = AsyncIOMotorClient('mongodb://localhost:27017')
        self.motor_db = self.motor_client[self.DB_NAME]
        api.database.db = self.motor_db

        # 初始化 Pipeline（给爬虫模拟用）
        self.pipeline = AnimePipeline()
        self.pipeline.client = self.sync_client
        self.pipeline.db = self.sync_db
        self.pipeline.anime_col = self.sync_db['anime']
        self.pipeline.domain_col = self.sync_db['discovered_domains']
        self.pipeline._ensure_indexes()

        # API 客户端
        transport = ASGITransport(app=app)
        self.api_client = AsyncClient(transport=transport, base_url='http://test')

    async def asyncTearDown(self):
        await self.api_client.aclose()
        self.motor_client.close()

    # --- 辅助方法 ---

    def _make_anime_item(self, title, year, director, genres=None, play_sources=None):
        item = AnimeItem()
        item['title'] = title
        item['original_title'] = title
        item['year'] = year
        item['director'] = director
        item['voice_actors'] = ['声优A', '声优B']
        item['synopsis'] = f'{title}的简介'
        item['poster_url'] = f'https://img.example.com/{title}.jpg'
        item['source_url'] = f'https://source.example.com/{title}'
        item['source_domain'] = 'source.example.com'
        item['genres'] = genres or ['动作']
        item['play_sources'] = play_sources or []
        item['discovered_at'] = datetime.now().isoformat()
        return item

    def _make_play_source(self, domain, episodes):
        return {
            'domain': domain,
            'episodes': [{'episode': str(e).zfill(2), 'url': f'https://{domain}/ep{e}.m3u8'} for e in episodes],
            'quality': '1080p',
            'raw_url': f'https://{domain}/play',
        }

    def _process(self, item):
        spider = MagicMock()
        return self.pipeline.process_item(item, spider)

    # --- 测试: 爬取 → 入库 → API 查询 ---

    async def test_full_flow_single_anime(self):
        """完整流程: 单个动画入库后可通过API查询"""
        # Step 1: 模拟爬虫产出
        item = self._make_anime_item(
            title='鬼灭之刃', year=2019, director='外崎春雄',
            genres=['动作', '奇幻'],
            play_sources=[self._make_play_source('player1.com', [1, 2, 3])],
        )

        # Step 2: Pipeline 入库
        self._process(item)

        # Step 3: API 查询列表
        resp = await self.api_client.get('/api/anime')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['meta']['total'], 1)
        self.assertEqual(data['data'][0]['title'], '鬼灭之刃')
        self.assertEqual(data['data'][0]['year'], 2019)
        self.assertEqual(data['data'][0]['play_source_count'], 1)

        # Step 4: API 查询详情
        anime_id = data['data'][0]['_id']
        resp = await self.api_client.get(f'/api/anime/{anime_id}')
        self.assertEqual(resp.status_code, 200)
        detail = resp.json()
        self.assertEqual(detail['director'], '外崎春雄')
        self.assertEqual(detail['synopsis'], '鬼灭之刃的简介')
        self.assertEqual(len(detail['play_sources']), 1)
        self.assertEqual(len(detail['play_sources'][0]['episodes']), 3)

        # Step 5: API 查询播放源
        resp = await self.api_client.get(f'/api/anime/{anime_id}/sources')
        self.assertEqual(resp.status_code, 200)
        sources = resp.json()
        self.assertEqual(sources[0]['domain'], 'player1.com')

    async def test_dedup_same_anime(self):
        """去重: 相同动画写入两次后只保留一条"""
        item1 = self._make_anime_item('鬼灭之刃', 2019, '外崎春雄')
        item2 = self._make_anime_item('鬼灭之刃', 2019, '外崎春雄')

        self._process(item1)
        self._process(item2)

        resp = await self.api_client.get('/api/anime')
        data = resp.json()
        self.assertEqual(data['meta']['total'], 1)

    async def test_different_anime_not_merged(self):
        """不同动画不合并"""
        item1 = self._make_anime_item('鬼灭之刃', 2019, '外崎春雄')
        item2 = self._make_anime_item('进击的巨人', 2013, '的場雅幸')

        self._process(item1)
        self._process(item2)

        resp = await self.api_client.get('/api/anime')
        data = resp.json()
        self.assertEqual(data['meta']['total'], 2)

    async def test_play_source_merge_by_domain(self):
        """播放源合并: 同域名的分集合并"""
        item1 = self._make_anime_item(
            '鬼灭之刃', 2019, '外崎春雄',
            play_sources=[self._make_play_source('player.com', [1, 2])],
        )
        item2 = self._make_anime_item(
            '鬼灭之刃', 2019, '外崎春雄',
            play_sources=[self._make_play_source('player.com', [3, 4])],
        )

        self._process(item1)
        self._process(item2)

        resp = await self.api_client.get('/api/anime')
        anime_id = resp.json()['data'][0]['_id']

        resp = await self.api_client.get(f'/api/anime/{anime_id}/sources')
        sources = resp.json()
        self.assertEqual(len(sources), 1)
        self.assertEqual(len(sources[0]['episodes']), 4)

    async def test_play_source_different_domains(self):
        """播放源: 不同域名保留为独立播放源"""
        item1 = self._make_anime_item(
            '鬼灭之刃', 2019, '外崎春雄',
            play_sources=[self._make_play_source('player1.com', [1, 2])],
        )
        item2 = self._make_anime_item(
            '鬼灭之刃', 2019, '外崎春雄',
            play_sources=[self._make_play_source('player2.com', [1, 2])],
        )

        self._process(item1)
        self._process(item2)

        resp = await self.api_client.get('/api/anime')
        anime_id = resp.json()['data'][0]['_id']

        resp = await self.api_client.get(f'/api/anime/{anime_id}/sources')
        sources = resp.json()
        self.assertEqual(len(sources), 2)

    # --- 测试: 域名入库 → API 查询 ---

    async def test_domain_flow(self):
        """域名入库后可通过API查询"""
        item = DomainItem()
        item['domain'] = 'anime-new.com'
        item['source'] = 'crt_sh'
        item['is_anime_site'] = True
        item['status'] = 'pending'

        self._process(item)

        resp = await self.api_client.get('/api/domains')
        data = resp.json()
        self.assertEqual(data['meta']['total'], 1)
        self.assertEqual(data['data'][0]['domain'], 'anime-new.com')

        resp = await self.api_client.get('/api/domains/anime-new.com')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['is_anime_site'])

    async def test_domain_dedup(self):
        """域名去重"""
        item1 = DomainItem()
        item1['domain'] = 'anime-new.com'
        item1['source'] = 'crt_sh'
        item1['is_anime_site'] = True

        item2 = DomainItem()
        item2['domain'] = 'anime-new.com'
        item2['source'] = 'dns_enum'
        item2['is_anime_site'] = True

        self._process(item1)
        self._process(item2)

        resp = await self.api_client.get('/api/domains')
        data = resp.json()
        self.assertEqual(data['meta']['total'], 1)

    # --- 测试: API 搜索筛选 ---

    async def test_search_by_keyword(self):
        """API 关键词搜索"""
        self._process(self._make_anime_item('鬼灭之刃', 2019, '外崎春雄'))
        self._process(self._make_anime_item('进击的巨人', 2013, '的場雅幸'))

        resp = await self.api_client.get('/api/anime?keyword=鬼灭')
        data = resp.json()
        self.assertEqual(data['meta']['total'], 1)
        self.assertEqual(data['data'][0]['title'], '鬼灭之刃')

    async def test_filter_by_year(self):
        """API 年份筛选"""
        self._process(self._make_anime_item('鬼灭之刃', 2019, '外崎春雄'))
        self._process(self._make_anime_item('进击的巨人', 2013, '的場雅幸'))

        resp = await self.api_client.get('/api/anime?year=2013')
        data = resp.json()
        self.assertEqual(data['meta']['total'], 1)
        self.assertEqual(data['data'][0]['title'], '进击的巨人')

    async def test_filter_by_genre(self):
        """API 类型筛选"""
        self._process(self._make_anime_item('鬼灭之刃', 2019, '外崎春雄', genres=['动作', '奇幻']))
        self._process(self._make_anime_item('日常', 2011, '石原立也', genres=['喜剧', '校园']))

        resp = await self.api_client.get('/api/anime?genre=喜剧')
        data = resp.json()
        self.assertEqual(data['meta']['total'], 1)
        self.assertEqual(data['data'][0]['title'], '日常')

    async def test_pagination(self):
        """API 分页"""
        for i in range(5):
            self._process(self._make_anime_item(f'动画{i}', 2020, f'导演{i}'))

        resp = await self.api_client.get('/api/anime?page=1&page_size=2')
        data = resp.json()
        self.assertEqual(len(data['data']), 2)
        self.assertEqual(data['meta']['total'], 5)
        self.assertEqual(data['meta']['total_pages'], 3)

    async def test_sort_by_year(self):
        """API 排序"""
        self._process(self._make_anime_item('旧动画', 2010, '导演A'))
        self._process(self._make_anime_item('新动画', 2023, '导演B'))

        resp = await self.api_client.get('/api/anime?sort_by=year&sort_order=asc')
        data = resp.json()
        self.assertEqual(data['data'][0]['year'], 2010)

    # --- 测试: 统计 API ---

    async def test_stats_after_data_ingestion(self):
        """数据入库后统计正确"""
        self._process(self._make_anime_item('鬼灭之刃', 2019, '外崎春雄', genres=['动作'],
                                            play_sources=[self._make_play_source('p1.com', [1, 2])]))
        self._process(self._make_anime_item('进击的巨人', 2013, '的場雅幸', genres=['动作', '热血'],
                                            play_sources=[self._make_play_source('p2.com', [1])]))

        d1 = DomainItem()
        d1['domain'] = 'a.com'
        d1['source'] = 'crt_sh'
        d1['is_anime_site'] = True
        d1['status'] = 'completed'
        self._process(d1)

        resp = await self.api_client.get('/api/stats')
        self.assertEqual(resp.status_code, 200)
        stats = resp.json()
        self.assertEqual(stats['total_anime'], 2)
        self.assertEqual(stats['total_domains'], 1)
        self.assertEqual(stats['anime_sites'], 1)
        self.assertEqual(stats['total_play_sources'], 2)

    # --- 测试: 索引验证 ---

    def test_indexes_created(self):
        """验证 MongoDB 索引已正确创建"""
        anime_indexes = self.sync_db['anime'].index_information()
        domain_indexes = self.sync_db['discovered_domains'].index_information()

        # 动画集合索引
        self.assertIn('dedup_key_1', anime_indexes)
        self.assertTrue(anime_indexes['dedup_key_1']['unique'])
        self.assertIn('title_1', anime_indexes)
        self.assertIn('year_1', anime_indexes)
        self.assertIn('director_1', anime_indexes)
        self.assertIn('genres_1', anime_indexes)
        self.assertIn('source_domain_1', anime_indexes)
        self.assertIn('play_sources.domain_1', anime_indexes)
        self.assertIn('year_-1_discovered_at_-1', anime_indexes)
        self.assertIn('discovered_at_1', anime_indexes)

        # 域名集合索引
        self.assertIn('domain_1', domain_indexes)
        self.assertTrue(domain_indexes['domain_1']['unique'])
        self.assertIn('status_1', domain_indexes)
        self.assertIn('is_anime_site_1', domain_indexes)
        self.assertIn('is_anime_site_1_status_1', domain_indexes)

    # --- 测试: 安全修复验证 ---

    async def test_regex_injection_safe(self):
        """验证 regex 注入被防御"""
        self._process(self._make_anime_item('测试动画', 2020, '导演'))

        # 恶意 regex 不会导致错误或返回全部数据
        resp = await self.api_client.get('/api/anime?keyword=.*')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # '.*' 被转义为字面量，不应匹配所有
        # 转义后搜索的是字面的 ".*"，不会匹配 "测试动画"
        self.assertEqual(data['meta']['total'], 0)

    async def test_regex_special_chars_safe(self):
        """验证特殊字符被正确转义"""
        self._process(self._make_anime_item('测试[动画]', 2020, '导演'))

        resp = await self.api_client.get('/api/anime?keyword=测试[动画]')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['meta']['total'], 1)

    async def test_domain_validation(self):
        """验证域名参数校验"""
        # 包含非法字符的域名
        resp = await self.api_client.get('/api/domains/invalid domain!')
        self.assertEqual(resp.status_code, 400)

    async def test_invalid_anime_id(self):
        """验证无效 ID 返回 400"""
        resp = await self.api_client.get('/api/anime/not_a_valid_id')
        self.assertEqual(resp.status_code, 400)

    # --- 测试: 数据补全流程 ---

    async def test_enrich_missing_fields(self):
        """首次只有标题和年份，后续补全声优/简介"""
        from unittest.mock import patch

        # 第一次：只有标题和年份（导演未知，dedup_key = MD5('新番动画_2024_')）
        item1 = AnimeItem()
        item1['title'] = '新番动画'
        item1['year'] = 2024
        item1['director'] = None
        item1['voice_actors'] = []
        item1['synopsis'] = None
        item1['genres'] = []
        item1['play_sources'] = []
        item1['poster_url'] = None
        item1['source_url'] = 'https://site1.com/anime/1'
        item1['source_domain'] = 'site1.com'
        item1['discovered_at'] = datetime.now().isoformat()
        with patch('anime_spider.pipelines.download_poster', return_value=None):
            self._process(item1)

        doc = self.sync_db['anime'].find_one({'title': '新番动画'})
        self.assertIsNone(doc.get('synopsis'))
        self.assertEqual(doc.get('voice_actors'), [])

        # 第二次：从另一个站补全声优和简介（相同 dedup_key）
        item2 = AnimeItem()
        item2['title'] = '新番动画'
        item2['year'] = 2024
        item2['director'] = None
        item2['voice_actors'] = ['声优X', '声优Y']
        item2['synopsis'] = '这是一个精彩的动画'
        item2['genres'] = ['热血']
        item2['play_sources'] = []
        item2['poster_url'] = None
        item2['source_url'] = 'https://site2.com/anime/2'
        item2['source_domain'] = 'site2.com'
        item2['discovered_at'] = datetime.now().isoformat()

        with patch('anime_spider.pipelines.download_poster', return_value=None):
            self._process(item2)

        # 验证字段已补全
        doc = self.sync_db['anime'].find_one({'title': '新番动画'})
        self.assertEqual(doc['voice_actors'], ['声优X', '声优Y'])
        self.assertEqual(doc['synopsis'], '这是一个精彩的动画')
        self.assertEqual(doc['genres'], ['热血'])
        # source_urls 应包含两个来源
        self.assertEqual(len(doc['source_urls']), 2)

    async def test_enrich_preserves_existing(self):
        """已有数据不应被覆盖"""
        from unittest.mock import patch

        item1 = self._make_anime_item('测试动画', 2020, '原导演')
        item1['synopsis'] = '原简介'
        with patch('anime_spider.pipelines.download_poster', return_value=None):
            self._process(item1)

        # 第二次：提供不同导演和简介
        item2 = self._make_anime_item('测试动画', 2020, '原导演')
        item2['director'] = '新导演'  # 不应覆盖
        item2['synopsis'] = '新简介'  # 不应覆盖

        with patch('anime_spider.pipelines.download_poster', return_value=None):
            self._process(item2)

        doc = self.sync_db['anime'].find_one({'title': '测试动画'})
        # 原有数据保留
        self.assertEqual(doc['director'], '原导演')
        self.assertEqual(doc['synopsis'], '原简介')

    async def test_enrich_genres_merge(self):
        """类型标签补全"""
        from unittest.mock import patch

        item1 = self._make_anime_item('测试动画', 2020, '导演', genres=[])
        item1['genres'] = []
        with patch('anime_spider.pipelines.download_poster', return_value=None):
            self._process(item1)

        item2 = self._make_anime_item('测试动画', 2020, '导演', genres=['热血', '冒险'])
        with patch('anime_spider.pipelines.download_poster', return_value=None):
            self._process(item2)

        doc = self.sync_db['anime'].find_one({'title': '测试动画'})
        self.assertEqual(doc['genres'], ['热血', '冒险'])

    async def test_poster_local_field_in_api(self):
        """API 应返回 poster_local 字段"""
        from unittest.mock import patch

        item = self._make_anime_item('海报测试', 2024, '导演')
        item['poster_url'] = 'https://example.com/poster.jpg'

        with patch('anime_spider.pipelines.download_poster', return_value='posters/abc123.jpg'):
            self._process(item)

        resp = await self.api_client.get('/api/anime')
        data = resp.json()
        found = [a for a in data['data'] if a['title'] == '海报测试']
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['poster_local'], 'posters/abc123.jpg')


if __name__ == '__main__':
    unittest.main()
