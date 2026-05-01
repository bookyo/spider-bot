"""测试去重工具模块"""

import unittest
from anime_spider.utils.dedup import (
    generate_anime_dedup_key,
    generate_domain_dedup_key,
    generate_provider_id,
    generate_source_id,
    generate_title_aliases,
    merge_play_sources,
    normalize_play_sources_for_storage,
    normalize_title,
    summarize_play_sources,
)


class TestGenerateAnimeDedupKey(unittest.TestCase):
    """测试动画去重键生成"""

    def test_basic(self):
        """基本去重键生成"""
        key = generate_anime_dedup_key('鬼灭之刃', 2019, '外崎春雄')
        self.assertIsNotNone(key)
        self.assertEqual(len(key), 32)  # MD5 长度

    def test_same_input_same_key(self):
        """相同输入应产生相同的键"""
        key1 = generate_anime_dedup_key('鬼灭之刃', 2019, '外崎春雄')
        key2 = generate_anime_dedup_key('鬼灭之刃', 2019, '外崎春雄')
        self.assertEqual(key1, key2)

    def test_different_input_different_key(self):
        """不同输入应产生不同的键"""
        key1 = generate_anime_dedup_key('鬼灭之刃', 2019, '外崎春雄')
        key2 = generate_anime_dedup_key('进击的巨人', 2013, '�的場雅幸')
        self.assertNotEqual(key1, key2)

    def test_none_values(self):
        """None 值应被处理为空字符串"""
        key = generate_anime_dedup_key(None, None, None)
        self.assertIsNotNone(key)

    def test_empty_strings(self):
        """空字符串应正常处理"""
        key = generate_anime_dedup_key('', '', '')
        self.assertIsNotNone(key)

    def test_whitespace_stripped(self):
        """空格应被去除"""
        key1 = generate_anime_dedup_key('鬼灭之刃', 2019, '外崎春雄')
        key2 = generate_anime_dedup_key(' 鬼灭之刃 ', 2019, ' 外崎春雄 ')
        self.assertEqual(key1, key2)

    def test_title_suffix_normalized(self):
        """站点标题后缀不应影响去重。"""
        key1 = generate_anime_dedup_key('鬼灭之刃', 2019, '外崎春雄')
        key2 = generate_anime_dedup_key('鬼灭之刃 - 樱花动漫', 2019, '外崎春雄')
        self.assertEqual(key1, key2)

    def test_season_marker_normalized(self):
        """季数标记应保留在归一化结果中。"""
        normalized = normalize_title('为美好的世界献上祝福 第2季')
        self.assertIn('_s2', normalized)

    def test_generate_title_aliases(self):
        aliases = generate_title_aliases('鬼灭之刃 - 樱花动漫', '鬼滅の刃')
        self.assertTrue(any('鬼灭之刃' in alias for alias in aliases))
        self.assertTrue(any('鬼滅の刃'.lower() in alias for alias in aliases))

    def test_partial_info(self):
        """部分信息缺失时仍能生成键"""
        key1 = generate_anime_dedup_key('鬼灭之刃', None, None)
        key2 = generate_anime_dedup_key('鬼灭之刃', 2019, None)
        self.assertNotEqual(key1, key2)


class TestGenerateDomainDedupKey(unittest.TestCase):
    """测试域名去重键生成"""

    def test_basic(self):
        key = generate_domain_dedup_key('Example.COM')
        self.assertEqual(key, 'example.com')

    def test_trailing_dot(self):
        key = generate_domain_dedup_key('example.com.')
        self.assertEqual(key, 'example.com')

    def test_whitespace(self):
        key = generate_domain_dedup_key('  example.com  ')
        self.assertEqual(key, 'example.com')


class TestMergePlaySources(unittest.TestCase):
    """测试播放源合并"""

    def test_empty_both(self):
        result = merge_play_sources([], [])
        self.assertEqual(result, [])

    def test_empty_existing(self):
        new = [{'domain': 'a.com', 'episodes': [{'episode': '01', 'url': 'http://a.com/01.m3u8'}]}]
        result = merge_play_sources([], new)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['domain'], 'a.com')

    def test_empty_new(self):
        existing = [{'domain': 'a.com', 'episodes': []}]
        result = merge_play_sources(existing, [])
        self.assertEqual(len(result), 1)

    def test_same_domain_merge_episodes(self):
        """同域名应合并分集"""
        existing = [
            {'domain': 'a.com', 'raw_url': 'http://a.com/line1', 'episodes': [{'episode': '01', 'url': 'http://a.com/01.m3u8'}]}
        ]
        new = [
            {'domain': 'a.com', 'raw_url': 'http://a.com/line1', 'episodes': [{'episode': '02', 'url': 'http://a.com/02.m3u8'}]}
        ]
        result = merge_play_sources(existing, new)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]['episodes']), 2)
        self.assertEqual(result[0]['episode_count'], 2)
        self.assertEqual(result[0]['latest_episode'], '02')
        self.assertEqual(result[0]['new_episode_count'], 1)

    def test_same_domain_dedup_episodes(self):
        """同域名同集数应去重"""
        existing = [
            {'domain': 'a.com', 'raw_url': 'http://a.com/line1', 'episodes': [{'episode': '01', 'url': 'http://a.com/01.m3u8'}]}
        ]
        new = [
            {'domain': 'a.com', 'raw_url': 'http://a.com/line1', 'episodes': [{'episode': '01', 'url': 'http://a.com/01_new.m3u8'}]}
        ]
        result = merge_play_sources(existing, new)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]['episodes']), 1)
        # 同集地址变化时，使用最新链接覆盖
        self.assertEqual(result[0]['episodes'][0]['url'], 'http://a.com/01_new.m3u8')
        self.assertEqual(result[0]['episodes'][0]['previous_url'], 'http://a.com/01.m3u8')

    def test_different_domains(self):
        """不同域名应保留两份"""
        existing = [
            {'domain': 'a.com', 'episodes': [{'episode': '01', 'url': 'http://a.com/01.m3u8'}]}
        ]
        new = [
            {'domain': 'b.com', 'episodes': [{'episode': '01', 'url': 'http://b.com/01.m3u8'}]}
        ]
        result = merge_play_sources(existing, new)
        self.assertEqual(len(result), 2)

    def test_same_domain_different_source_kept_separate(self):
        existing = [
            {'domain': 'a.com', 'raw_url': 'http://a.com/line1', 'source_name': '线路1', 'episodes': [{'episode': '01', 'url': 'http://a.com/01.m3u8'}]}
        ]
        new = [
            {'domain': 'a.com', 'raw_url': 'http://a.com/line2', 'source_name': '线路2', 'episodes': [{'episode': '01', 'url': 'http://a.com/l2-01.m3u8'}]}
        ]
        result = merge_play_sources(existing, new)
        self.assertEqual(len(result), 2)

    def test_none_values(self):
        """None 值应正常处理"""
        result = merge_play_sources(None, None)
        self.assertEqual(result, [])

    def test_summarize_play_sources(self):
        sources = [
            {
                'domain': 'a.com',
                'source_name': '线路1',
                'episodes': [{'episode': '01', 'url': 'http://a.com/01.m3u8'}],
                'new_episode_count': 1,
            },
            {
                'domain': 'b.com',
                'source_name': '线路2',
                'episodes': [{'episode': '03', 'url': 'http://b.com/03.m3u8'}],
                'new_episode_count': 2,
            },
        ]
        summary = summarize_play_sources(sources)
        self.assertEqual(summary['total_episode_count'], 2)
        self.assertEqual(summary['latest_episode'], '03')
        self.assertEqual(summary['new_episode_count'], 3)

    def test_summarize_play_sources_dedup_episode_across_sources(self):
        sources = [
            {
                'domain': 'a.com',
                'source_name': '线路1',
                'episodes': [{'episode': '01', 'url': 'http://a.com/01.m3u8'}],
                'new_episode_count': 1,
            },
            {
                'domain': 'a.com',
                'source_name': '线路2',
                'episodes': [{'episode': '01', 'url': 'http://a.com/l2-01.m3u8'}],
                'new_episode_count': 1,
            },
        ]
        summary = summarize_play_sources(sources)
        self.assertEqual(summary['total_episode_count'], 1)
        self.assertEqual(summary['latest_episode'], '01')

    def test_generate_provider_and_source_ids(self):
        source = {
            'domain': 'page.example.com',
            'source_name': '线路1',
            'raw_url': 'https://site.example.com/post/1',
            'episodes': [{'episode': '01', 'url': 'https://media.example.com/1.m3u8'}],
        }
        self.assertEqual(generate_provider_id(source), 'provider:media.example.com')
        self.assertIsNotNone(generate_source_id(source))

    def test_same_episode_host_merges_same_provider(self):
        existing = [
            {
                'domain': 'v.ikanbot.com',
                'source_name': '线路1',
                'anime_key': '420030',
                'raw_url': 'https://v.ikanbot.com/play/420030',
                'episodes': [{'episode': '01', 'url': 'https://play.xluuss.com/play/a/index.m3u8'}],
            }
        ]
        new = [
            {
                'domain': 'v.ikanbot.com',
                'source_name': '线路9',
                'anime_key': '420030',
                'raw_url': 'https://v.ikanbot.com/play/420030',
                'episodes': [{'episode': '02', 'url': 'https://play.xluuss.com/play/b/index.m3u8'}],
            }
        ]
        result = merge_play_sources(existing, new)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['provider_id'], 'provider:play.xluuss.com')
        self.assertEqual(result[0]['episode_count'], 2)

    def test_different_episode_host_kept_separate_even_same_page_domain(self):
        existing = [
            {
                'domain': 'v.ikanbot.com',
                'source_name': '线路1',
                'anime_key': '420030',
                'raw_url': 'https://v.ikanbot.com/play/420030',
                'episodes': [{'episode': '01', 'url': 'https://play.xluuss.com/play/a/index.m3u8'}],
            }
        ]
        new = [
            {
                'domain': 'v.ikanbot.com',
                'source_name': '线路2',
                'anime_key': '420030',
                'raw_url': 'https://v.ikanbot.com/play/420030',
                'episodes': [{'episode': '01', 'url': 'https://v.gsuus.com/play/a/index.m3u8'}],
            }
        ]
        result = merge_play_sources(existing, new)
        self.assertEqual(len(result), 2)

    def test_normalize_play_sources_for_storage_ignores_stale_source_id(self):
        sources = [
            {
                'domain': 'www.iqiyi.com',
                'source_name': '奇艺视频',
                'raw_url': 'https://www.yinghuadh.com/play/187546-1-1.html',
                'line_from': 'qiyi',
                'line_sid': 1,
                'line_id': 'qiyi|1|奇艺视频',
                'anime_key': '187546',
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
                'anime_key': '187546',
                'source_id': 'stale-b',
                'episodes': [{'episode': '62', 'url': 'https://www.iqiyi.com/v_62.html'}],
            },
        ]

        normalized = normalize_play_sources_for_storage(sources, anime_key='187546')
        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]['provider_id'], 'provider:www.iqiyi.com')
        self.assertEqual(normalized[0]['episode_count'], 2)
        self.assertEqual(len(normalized[0]['episodes']), 2)

    def test_normalize_play_sources_for_storage_replaces_source_stub(self):
        sources = [
            {
                'domain': 'www.yinghuadh.com',
                'source_name': 'source-1',
                'raw_url': 'https://www.yinghuadh.com/post/187546.html',
                'anime_key': '187546',
                'episodes': [
                    {'episode': '01', 'url': 'https://www.yinghuadh.com/play/187546-1-1.html'},
                    {'episode': '02', 'url': 'https://www.yinghuadh.com/play/187546-1-2.html'},
                ],
            },
            {
                'domain': 'www.iqiyi.com',
                'source_name': '奇艺视频',
                'raw_url': 'https://www.yinghuadh.com/play/187546-1-1.html',
                'line_from': 'qiyi',
                'line_sid': 1,
                'line_id': 'qiyi|1|奇艺视频',
                'anime_key': '187546',
                'episodes': [
                    {'episode': '01', 'url': 'https://www.yinghuadh.com/play/187546-1-1.html'},
                    {'episode': '02', 'url': 'https://www.yinghuadh.com/play/187546-1-2.html'},
                ],
                'provider_key': 'www.iqiyi.com',
            },
        ]

        normalized = normalize_play_sources_for_storage(sources, anime_key='187546')
        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]['source_name'], '奇艺视频')
        self.assertEqual(normalized[0]['provider_id'], 'provider:www.iqiyi.com')


if __name__ == '__main__':
    unittest.main()
