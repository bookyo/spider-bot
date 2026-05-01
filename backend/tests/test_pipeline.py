"""测试数据管道模块 - 需要 MongoDB 运行"""

import unittest
from unittest.mock import MagicMock
from datetime import datetime
from pymongo import MongoClient
from scrapy.utils.project import get_project_settings

from anime_spider.items import AnimeItem, DomainItem
from anime_spider.pipelines import AnimePipeline
from anime_spider.utils.dedup import generate_anime_dedup_key


class TestAnimePipeline(unittest.TestCase):
    """测试动画数据管道 - 集成测试（需要 MongoDB）"""

    @classmethod
    def setUpClass(cls):
        """连接测试数据库"""
        settings = get_project_settings()
        uri = settings.get('MONGODB_URI', 'mongodb://localhost:27017')
        cls.client = MongoClient(uri)
        cls.db = cls.client['anime_db_test']  # 使用测试数据库
        cls.anime_col = cls.db['anime_test']
        cls.domain_col = cls.db['domains_test']

        # 创建索引
        cls.anime_col.create_index('dedup_key', unique=True)
        cls.domain_col.create_index('domain', unique=True)

    @classmethod
    def tearDownClass(cls):
        """清理测试数据库"""
        cls.db.drop_collection('anime_test')
        cls.db.drop_collection('domains_test')
        cls.client.close()

    def setUp(self):
        """每个测试前清空集合"""
        self.anime_col.delete_many({})
        self.domain_col.delete_many({})

        # 创建 pipeline 实例
        self.pipeline = AnimePipeline()
        self.pipeline.client = self.client
        self.pipeline.db = self.db
        self.pipeline.anime_col = self.anime_col
        self.pipeline.domain_col = self.domain_col

    def _create_anime_item(self, title='测试动画', year=2024, director='测试导演'):
        """创建测试用的动画数据项"""
        item = AnimeItem()
        item['title'] = title
        item['original_title'] = title
        item['year'] = year
        item['director'] = director
        item['voice_actors'] = ['声优A', '声优B']
        item['synopsis'] = '这是一个测试简介'
        item['poster_url'] = 'https://example.com/poster.jpg'
        item['source_url'] = 'https://example.com/anime/123'
        item['source_domain'] = 'example.com'
        item['genres'] = ['动作', '奇幻']
        item['play_sources'] = [
            {
                'domain': 'player.example.com',
                'episodes': [
                    {'episode': '01', 'url': 'https://player.example.com/ep01.m3u8'},
                    {'episode': '02', 'url': 'https://player.example.com/ep02.m3u8'},
                ],
                'quality': '1080p',
                'raw_url': 'https://example.com/play/123',
            }
        ]
        item['dedup_key'] = generate_anime_dedup_key(title, year, director)
        item['discovered_at'] = datetime.now().isoformat()
        return item

    def test_insert_new_anime(self):
        """测试插入新动画"""
        item = self._create_anime_item()
        spider = MagicMock()
        self.pipeline.process_item(item, spider)

        # 验证数据库中存在该记录
        doc = self.anime_col.find_one({'dedup_key': item['dedup_key']})
        self.assertIsNotNone(doc)
        self.assertEqual(doc['title'], '测试动画')
        self.assertEqual(doc['year'], 2024)
        self.assertEqual(doc['director'], '测试导演')
        self.assertEqual(len(doc['play_sources']), 1)
        self.assertEqual(len(doc['play_sources'][0]['episodes']), 2)

    def test_dedup_same_anime(self):
        """测试相同动画去重"""
        item1 = self._create_anime_item(title='鬼灭之刃', year=2019, director='外崎春雄')
        item2 = self._create_anime_item(title='鬼灭之刃', year=2019, director='外崎春雄')
        item2['source_url'] = 'https://another-site.com/anime/456'

        spider = MagicMock()
        self.pipeline.process_item(item1, spider)
        self.pipeline.process_item(item2, spider)

        # 应该只有一条记录
        count = self.anime_col.count_documents({'title': '鬼灭之刃'})
        self.assertEqual(count, 1)

        # 但 source_urls 应该包含两个来源
        doc = self.anime_col.find_one({'title': '鬼灭之刃'})
        self.assertIn('https://example.com/anime/123', doc['source_urls'])
        self.assertIn('https://another-site.com/anime/456', doc['source_urls'])

    def test_different_anime_not_deduped(self):
        """不同动画不应被去重"""
        item1 = self._create_anime_item(title='鬼灭之刃', year=2019, director='外崎春雄')
        item2 = self._create_anime_item(title='进击的巨人', year=2013, director='的場雅幸')

        spider = MagicMock()
        self.pipeline.process_item(item1, spider)
        self.pipeline.process_item(item2, spider)

        count = self.anime_col.count_documents({})
        self.assertEqual(count, 2)

    def test_merge_play_sources(self):
        """测试播放源合并"""
        item1 = self._create_anime_item()
        item1['play_sources'] = [
            {
                'domain': 'player1.example.com',
                'episodes': [{'episode': '01', 'url': 'https://p1.com/01.m3u8'}],
            }
        ]

        item2 = self._create_anime_item()
        item2['play_sources'] = [
            {
                'domain': 'player2.example.com',
                'episodes': [{'episode': '01', 'url': 'https://p2.com/01.m3u8'}],
            }
        ]

        spider = MagicMock()
        self.pipeline.process_item(item1, spider)
        self.pipeline.process_item(item2, spider)

        doc = self.anime_col.find_one({'dedup_key': item1['dedup_key']})
        # 应该有两个播放源（不同域名）
        self.assertEqual(len(doc['play_sources']), 2)

    def test_merge_play_sources_same_domain(self):
        """测试同域名播放源合并"""
        item1 = self._create_anime_item()
        item1['play_sources'] = [
            {
                'domain': 'player.example.com',
                'episodes': [{'episode': '01', 'url': 'https://p.com/01.m3u8'}],
            }
        ]

        item2 = self._create_anime_item()
        item2['play_sources'] = [
            {
                'domain': 'player.example.com',
                'episodes': [{'episode': '02', 'url': 'https://p.com/02.m3u8'}],
            }
        ]

        spider = MagicMock()
        self.pipeline.process_item(item1, spider)
        self.pipeline.process_item(item2, spider)

        doc = self.anime_col.find_one({'dedup_key': item1['dedup_key']})
        # 同域名应该合并为一个播放源
        self.assertEqual(len(doc['play_sources']), 1)
        # 但应该有两个分集
        self.assertEqual(len(doc['play_sources'][0]['episodes']), 2)

    def test_normalize_existing_sources_collapses_stale_source_ids(self):
        doc = {
            'title': '测试动画',
            'year': 2024,
            'director': '测试导演',
            'dedup_key': generate_anime_dedup_key('测试动画', 2024, '测试导演'),
            'source_urls': ['https://www.yinghuadh.com/post/187546.html'],
            'play_sources': [
                {
                    'domain': 'www.iqiyi.com',
                    'source_name': '奇艺视频',
                    'raw_url': 'https://www.yinghuadh.com/play/187546-1-1.html',
                    'line_from': 'qiyi',
                    'line_sid': 1,
                    'line_id': 'qiyi|1|奇艺视频',
                    'source_id': 'stale-a',
                    'episodes': [{'episode': '01', 'url': 'https://www.iqiyi.com/v_1.html'}],
                },
                {
                    'domain': 'www.iqiyi.com',
                    'source_name': '奇艺视频',
                    'raw_url': 'https://www.yinghuadh.com/play/187546-1-62.html',
                    'line_from': 'qiyi',
                    'line_sid': 1,
                    'line_id': 'qiyi|1|奇艺视频',
                    'source_id': 'stale-b',
                    'episodes': [{'episode': '62', 'url': 'https://www.iqiyi.com/v_62.html'}],
                },
            ],
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
        }
        insert_result = self.anime_col.insert_one(doc)
        stored = self.anime_col.find_one({'_id': insert_result.inserted_id})

        self.pipeline._normalize_existing_sources(stored)

        updated = self.anime_col.find_one({'_id': insert_result.inserted_id})
        self.assertEqual(len(updated['play_sources']), 1)
        self.assertEqual(updated['total_episode_count'], 2)
        self.assertEqual(updated['latest_episode'], '62')

    def test_process_domain_item(self):
        """测试域名数据处理"""
        item = DomainItem()
        item['domain'] = 'anime-test.com'
        item['source'] = 'crt_sh'
        item['discovered_at'] = datetime.now().isoformat()
        item['is_anime_site'] = True
        item['last_crawled'] = None
        item['status'] = 'pending'

        spider = MagicMock()
        self.pipeline.process_item(item, spider)

        doc = self.domain_col.find_one({'domain': 'anime-test.com'})
        self.assertIsNotNone(doc)
        self.assertTrue(doc['is_anime_site'])
        self.assertEqual(doc['status'], 'pending')

    def test_process_domain_duplicate(self):
        """测试域名去重"""
        item1 = DomainItem()
        item1['domain'] = 'anime-test.com'
        item1['source'] = 'crt_sh'
        item1['is_anime_site'] = True

        item2 = DomainItem()
        item2['domain'] = 'anime-test.com'
        item2['source'] = 'dns_enum'
        item2['is_anime_site'] = True

        spider = MagicMock()
        self.pipeline.process_item(item1, spider)
        self.pipeline.process_item(item2, spider)

        count = self.domain_col.count_documents({'domain': 'anime-test.com'})
        self.assertEqual(count, 1)

    def test_update_missing_fields(self):
        """测试更新缺失字段"""
        item1 = self._create_anime_item()
        item1['synopsis'] = None
        item1['poster_url'] = None

        item2 = self._create_anime_item()
        item2['synopsis'] = '新添加的简介'
        item2['poster_url'] = 'https://new-poster.jpg'

        spider = MagicMock()
        self.pipeline.process_item(item1, spider)
        self.pipeline.process_item(item2, spider)

        doc = self.anime_col.find_one({'dedup_key': item1['dedup_key']})
        self.assertEqual(doc['synopsis'], '新添加的简介')
        self.assertEqual(doc['poster_url'], 'https://new-poster.jpg')

    def test_detail_item_repairs_legacy_follow_only_doc(self):
        """详情页应能修复旧的 title=None 补源文档。"""
        dedup_key = generate_anime_dedup_key('炼气十万年', 2023, None)
        self.anime_col.insert_one({
            'title': None,
            'original_title': None,
            'aliases': [],
            'normalized_title': None,
            'year': 2023,
            'director': None,
            'voice_actors': [],
            'synopsis': None,
            'poster_url': None,
            'poster_local': None,
            'source_urls': ['https://www.yhdm7.net/article/lianqishiwannian.html'],
            'source_domain': 'www.yhdm7.net',
            'genres': [],
            'play_sources': [],
            'latest_episode': None,
            'total_episode_count': 0,
            'new_episode_count': 0,
            'incremental_found': False,
            'last_incremental_check': datetime.now(),
            'incremental_priority': 0.0,
            'dedup_key': dedup_key,
            'extractor_name': 'play_page_follow',
            'extractor_confidence': None,
            'site_type': 'play_page_follow',
            'quality_score': 0.0,
            'discovered_at': datetime.now(),
            'updated_at': datetime.now(),
        })

        item = self._create_anime_item(title='炼气十万年', year=2023, director=None)
        item['original_title'] = '炼气十万年'
        item['normalized_title'] = '炼气十万年'
        item['synopsis'] = '十万年前，天岚宗叱咤修真界。'
        item['source_url'] = 'https://www.yhdm7.net/article/lianqishiwannian.html'
        item['source_domain'] = 'www.yhdm7.net'
        item['dedup_key'] = dedup_key

        spider = MagicMock()
        self.pipeline.process_item(item, spider)

        doc = self.anime_col.find_one({'dedup_key': dedup_key})
        self.assertEqual(doc['title'], '炼气十万年')
        self.assertEqual(doc['original_title'], '炼气十万年')
        self.assertEqual(doc['normalized_title'], '炼气十万年')
        self.assertEqual(doc['synopsis'], '十万年前，天岚宗叱咤修真界。')

    def test_weak_match_merges_same_title_when_existing_year_missing(self):
        existing = self._create_anime_item(title='咒术回战', year=None, director='朴性厚')
        existing['dedup_key'] = generate_anime_dedup_key('咒术回战', None, '朴性厚')
        incoming = self._create_anime_item(title='咒术回战', year=2020, director='朴性厚')
        incoming['dedup_key'] = generate_anime_dedup_key('咒术回战', 2020, '朴性厚')
        incoming['source_url'] = 'https://another.example.com/anime/999'

        spider = MagicMock()
        self.pipeline.process_item(existing, spider)
        self.pipeline.process_item(incoming, spider)

        count = self.anime_col.count_documents({'normalized_title': '咒术回战'})
        self.assertEqual(count, 1)
        doc = self.anime_col.find_one({'normalized_title': '咒术回战'})
        self.assertIn('https://another.example.com/anime/999', doc['source_urls'])
        self.assertEqual(doc['year'], 2020)

    def test_weak_match_merges_by_alias(self):
        existing = self._create_anime_item(title='鬼灭之刃 - 樱花动漫', year=2019, director=None)
        existing['original_title'] = '鬼滅の刃'
        existing['dedup_key'] = generate_anime_dedup_key('鬼灭之刃 - 樱花动漫', 2019, None)
        incoming = self._create_anime_item(title='鬼灭之刃', year=2019, director=None)
        incoming['original_title'] = '鬼滅の刃'
        incoming['dedup_key'] = generate_anime_dedup_key('鬼灭之刃', 2019, None)
        incoming['source_url'] = 'https://alias.example.com/anime/456'

        spider = MagicMock()
        self.pipeline.process_item(existing, spider)
        self.pipeline.process_item(incoming, spider)

        count = self.anime_col.count_documents({'year': 2019})
        self.assertEqual(count, 1)
        doc = self.anime_col.find_one({'year': 2019})
        self.assertIn('https://alias.example.com/anime/456', doc['source_urls'])

    def test_weak_match_does_not_merge_different_seasons(self):
        item1 = self._create_anime_item(title='为美好的世界献上祝福 第1季', year=2016, director='金崎贵臣')
        item1['dedup_key'] = generate_anime_dedup_key('为美好的世界献上祝福 第1季', 2016, '金崎贵臣')
        item2 = self._create_anime_item(title='为美好的世界献上祝福 第2季', year=2017, director='金崎贵臣')
        item2['dedup_key'] = generate_anime_dedup_key('为美好的世界献上祝福 第2季', 2017, '金崎贵臣')

        spider = MagicMock()
        self.pipeline.process_item(item1, spider)
        self.pipeline.process_item(item2, spider)

        count = self.anime_col.count_documents({'title': {'$regex': '为美好的世界献上祝福'}})
        self.assertEqual(count, 2)

    def test_weak_match_does_not_merge_when_year_conflicts(self):
        item1 = self._create_anime_item(title='测试番剧', year=2021, director=None)
        item1['dedup_key'] = generate_anime_dedup_key('测试番剧', 2021, None)
        item2 = self._create_anime_item(title='测试番剧', year=2023, director=None)
        item2['dedup_key'] = generate_anime_dedup_key('测试番剧', 2023, None)

        spider = MagicMock()
        self.pipeline.process_item(item1, spider)
        self.pipeline.process_item(item2, spider)

        count = self.anime_col.count_documents({'normalized_title': '测试番剧'})
        self.assertEqual(count, 2)


if __name__ == '__main__':
    unittest.main()
