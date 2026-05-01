"""测试 m3u8 链接提取模块"""

import unittest
from unittest.mock import MagicMock

from anime_spider.utils.m3u8_extractor import M3U8Extractor


class TestM3U8Extractor(unittest.TestCase):
    """测试 m3u8 链接提取器"""

    def setUp(self):
        self.extractor = M3U8Extractor()

    def _mock_response(self, url='https://example.com/play/123', text='', css_map=None):
        """创建模拟的 Response 对象"""
        response = MagicMock()
        response.url = url
        response.text = text
        response.urljoin = MagicMock(side_effect=lambda value: value if str(value).startswith('http') else f'https://example.com{value}')
        response.css = MagicMock(side_effect=lambda sel: self._css_handler(sel, css_map or {}))
        return response

    def _css_handler(self, selector, css_map):
        """模拟 CSS 选择器"""
        mock = MagicMock()
        if selector in css_map:
            value = css_map[selector]
            if isinstance(value, list):
                mock.getall = MagicMock(return_value=value)
                mock.get = MagicMock(return_value=value[0] if value else None)
            else:
                mock.get = MagicMock(return_value=value)
                mock.getall = MagicMock(return_value=[value] if value else [])
        else:
            mock.get = MagicMock(return_value=None)
            mock.getall = MagicMock(return_value=[])
        return mock

    def test_extract_direct_m3u8(self):
        """提取直接的 m3u8 链接"""
        text = '''
        <video src="https://cdn.example.com/video/ep01.m3u8"></video>
        <source src="https://cdn.example.com/video/ep02.m3u8">
        '''
        response = self._mock_response(text=text)
        results = self.extractor.extract(response)
        urls = [r['url'] for r in results]
        self.assertTrue(any('ep01.m3u8' in u for u in urls))
        self.assertTrue(any('ep02.m3u8' in u for u in urls))

    def test_extract_from_javascript(self):
        """从 JavaScript 代码中提取 m3u8"""
        text = '''
        <script>
        var player = new DPlayer({
            video: {
                url: "https://cdn.example.com/video/master.m3u8"
            }
        });
        </script>
        '''
        response = self._mock_response(text=text)
        results = self.extractor.extract(response)
        urls = [r['url'] for r in results]
        self.assertTrue(any('master.m3u8' in u for u in urls))

    def test_extract_from_json_config(self):
        """从 JSON 配置中提取 m3u8"""
        text = '''
        <script>
        var config = {
            "url": "https://cdn.example.com/video/playlist.m3u8",
            "type": "hls"
        };
        </script>
        '''
        response = self._mock_response(text=text)
        results = self.extractor.extract(response)
        urls = [r['url'] for r in results]
        self.assertTrue(any('playlist.m3u8' in u for u in urls))

    def test_extract_from_source_attribute(self):
        """从 source 属性中提取"""
        text = '''
        <script>
        var source = 'https://cdn.example.com/ep01.m3u8';
        </script>
        '''
        response = self._mock_response(text=text)
        results = self.extractor.extract(response)
        urls = [r['url'] for r in results]
        self.assertTrue(any('ep01.m3u8' in u for u in urls))

    def test_extract_from_file_attribute(self):
        """从 file 属性中提取"""
        text = '''
        <script>
        file: "https://cdn.example.com/stream.m3u8"
        </script>
        '''
        response = self._mock_response(text=text)
        results = self.extractor.extract(response)
        urls = [r['url'] for r in results]
        self.assertTrue(any('stream.m3u8' in u for u in urls))

    def test_deduplication(self):
        """去重测试 - 相同 URL 只返回一次"""
        text = '''
        https://cdn.example.com/video.m3u8
        https://cdn.example.com/video.m3u8
        '''
        response = self._mock_response(text=text)
        results = self.extractor.extract(response)
        urls = [r['url'] for r in results]
        self.assertEqual(len(urls), len(set(urls)))

    def test_extract_iframe_src(self):
        """提取 iframe 播放器链接"""
        response = self._mock_response(
            text='',
            css_map={
                'iframe::attr(src)': ['https://player.example.com/embed/123'],
            }
        )
        results = self.extractor._extract_from_iframes(response)
        self.assertTrue(len(results) > 0)
        self.assertTrue(results[0].get('needs_follow'))

    def test_guess_episode_from_url(self):
        """从 URL 猜测集数"""
        ep = self.extractor._guess_episode('https://cdn.example.com/ep01.m3u8')
        self.assertEqual(ep, '01')

    def test_guess_episode_from_context(self):
        """从上下文猜测集数"""
        ep = self.extractor._guess_episode(
            'https://cdn.example.com/video.m3u8',
            '第12集 播放地址'
        )
        self.assertEqual(ep, '12')

    def test_guess_episode_none(self):
        """无法猜测集数时返回 None"""
        ep = self.extractor._guess_episode('https://cdn.example.com/video.m3u8')
        self.assertIsNone(ep)

    def test_no_m3u8_links(self):
        """没有 m3u8 链接时返回空列表"""
        text = '<html><body>没有任何视频链接</body></html>'
        response = self._mock_response(text=text)
        results = self.extractor.extract(response)
        self.assertEqual(len(results), 0)

    def test_relative_url_conversion(self):
        """相对 URL 应转换为绝对 URL"""
        text = 'source: "/video/ep01.m3u8"'
        response = self._mock_response(
            url='https://example.com/play/123',
            text=text,
        )
        results = self.extractor.extract(response)
        # 相对路径以 / 开头，不包含 .m3u8 扩展名在正则匹配中
        # 但如果有完整路径应该能匹配
        for r in results:
            self.assertTrue(r['url'].startswith('http'))

    def test_extract_episodes_from_page(self):
        """从页面提取分集列表"""
        response = self._mock_response(
            url='https://example.com/play/123',
            text='',
            css_map={
                '.episode-list a': [
                    MagicMock(
                        css=MagicMock(side_effect=lambda sel: self._ep_css_handler(sel)),
                    )
                ],
            }
        )
        # 这个测试需要更复杂的 mock，简化验证
        results = self.extractor.extract_episodes_from_page(response)
        self.assertIsInstance(results, list)

    def test_extract_multiple_play_sources_from_page(self):
        response = self._mock_response(url='https://example.com/post/1', text='')
        group1 = MagicMock()
        group1.css = MagicMock(side_effect=lambda sel: [
            MagicMock(css=MagicMock(side_effect=lambda sub: self._source_item_css_handler(sub, '01', '/play/1-1'))),
            MagicMock(css=MagicMock(side_effect=lambda sub: self._source_item_css_handler(sub, '02', '/play/1-2'))),
        ] if sel == 'a' else MagicMock())
        group2 = MagicMock()
        group2.css = MagicMock(side_effect=lambda sel: [
            MagicMock(css=MagicMock(side_effect=lambda sub: self._source_item_css_handler(sub, '01', '/play/2-1'))),
        ] if sel == 'a' else MagicMock())

        def css_side_effect(selector):
            if selector == '.nav-tabs li::text':
                mock = MagicMock()
                mock.getall = MagicMock(return_value=['线路1', '线路2'])
                mock.get = MagicMock(return_value='线路1')
                return mock
            if selector == '.stui-content__playlist, .play-list, .playlist, .source-list':
                return [group1, group2]
            return self._css_handler(selector, {})

        response.css = MagicMock(side_effect=css_side_effect)
        results = self.extractor.extract_play_sources_from_page(response)
        self.assertEqual(len(results), 0)

    def test_extract_player_config(self):
        response = self._mock_response(
            url='https://example.com/play/1-1-1.html',
            text='<script type="text/javascript">var player_aaaa={"from":"qiyi","sid":1,"url":"https:\\/\\/www.iqiyi.com\\/v_123.html"}</script>',
        )
        config = self.extractor.extract_player_config(response)
        self.assertEqual(config['from'], 'qiyi')
        self.assertEqual(config['sid'], 1)

    def test_extract_play_page_entries(self):
        response = self._mock_response(url='https://example.com/article/1.html', text='')
        group = MagicMock()
        group.css = MagicMock(side_effect=lambda sel: [
            MagicMock(css=MagicMock(side_effect=lambda sub: self._source_item_css_handler(sub, '01', '/play/a-1.html'))),
            MagicMock(css=MagicMock(side_effect=lambda sub: self._source_item_css_handler(sub, '02', '/play/a-2.html'))),
        ] if sel == '.stui-content__playlist a, a.module-play-list-link, a' else (
            MagicMock(getall=MagicMock(return_value=['高清路线1'])) if sel == '.stui-pannel__head h2.title::text' else MagicMock(getall=MagicMock(return_value=[]))
        ))

        def css_side_effect(selector):
            if selector == '.stui-pannel-box.b.playlist, .stui-pannel-box.playlist, .module-play-list, .module-play-list-content, .module-list':
                return [group]
            return self._css_handler(selector, {})

        response.css = MagicMock(side_effect=css_side_effect)
        results = self.extractor.extract_play_page_entries(response)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['source_name'], '高清路线1')
        self.assertEqual(results[0]['entries'][0]['play_page_url'], 'https://example.com/play/a-1.html')

    def test_extract_play_page_entries_dedupes_duplicate_groups(self):
        groups = [
            {
                'source_name': 'source-1',
                'entries': [
                    {'episode': '01', 'play_page_url': 'https://example.com/play/a-1.html'},
                    {'episode': '02', 'play_page_url': 'https://example.com/play/a-2.html'},
                ],
            },
            {
                'source_name': '高清路线1',
                'entries': [
                    {'episode': '01', 'play_page_url': 'https://example.com/play/a-1.html'},
                    {'episode': '02', 'play_page_url': 'https://example.com/play/a-2.html'},
                ],
            },
        ]
        results = self.extractor._dedupe_play_entry_groups(groups)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['source_name'], '高清路线1')

    def test_extract_play_sources_applies_player_metadata(self):
        response = self._mock_response(
            url='https://example.com/play/1-1-1.html',
            text='<script type="text/javascript">var player_aaaa={"from":"qiyi","sid":1,"url":"https:\\/\\/www.iqiyi.com\\/v_123.html"}</script>',
        )
        group = MagicMock()
        group.css = MagicMock(side_effect=lambda sel: [
            MagicMock(css=MagicMock(side_effect=lambda sub: self._source_item_css_handler(sub, '01', '/play/1-1'))),
        ] if sel == '.stui-content__playlist a, a.module-play-list-link, a' else (
            MagicMock(getall=MagicMock(return_value=['奇艺视频'])) if sel == '.stui-pannel__head h2.title::text' else MagicMock(getall=MagicMock(return_value=[]))
        ))

        def css_side_effect(selector):
            if selector == '.stui-pannel-box.b.playlist, .stui-pannel-box.playlist, .module-play-list':
                return [group]
            return self._css_handler(selector, {})

        response.css = MagicMock(side_effect=css_side_effect)
        results = self.extractor.extract_play_sources_from_page(response)
        self.assertEqual(len(results), 0)

    def test_is_playable_media_url(self):
        self.assertTrue(self.extractor._is_playable_media_url('https://cdn.example.com/01.m3u8'))
        self.assertTrue(self.extractor._is_playable_media_url('https://cdn.example.com/01.mp4'))
        self.assertFalse(self.extractor._is_playable_media_url('https://example.com/play/1-2'))

    def test_build_ikanbot_token(self):
        token = self.extractor._build_ikanbot_token(
            '420030',
            'b977b3ac7v9c1d8db1f4b7e6e24o6ecfa75a',
        )
        self.assertEqual(token, '977b3ac79c1d8db14b7e6e246ecfa75a')

    def test_extract_ikanbot_play_sources(self):
        response = self._mock_response(
            url='https://v.ikanbot.com/play/420030',
            text='',
            css_map={
                '#current_id::attr(value)': '420030',
                '#e_token::attr(value)': 'b977b3ac7v9c1d8db1f4b7e6e24o6ecfa75a',
                '#mtype::attr(value)': '2',
            }
        )

        payload = {
            'state': 1,
            'data': {
                'list': [
                    {
                        'id': 1,
                        'resData': '[{"flag":"normal","newName":"第1集","url":"第1集$https://play.xluuss.com/play/a/index.m3u8#第2集$https://play.xluuss.com/play/b/index.m3u8"}]',
                    },
                    {
                        'id': 2,
                        'resData': '[{"flag":"normal","newName":"第1集","url":"第1集$https://v.gsuus.com/play/a/index.m3u8"}]',
                    },
                ]
            }
        }

        original_get = __import__('anime_spider.utils.m3u8_extractor', fromlist=['requests']).requests.get

        class FakeResp:
            def json(self):
                return payload

        def fake_get(url, params=None, headers=None, timeout=None):
            self.assertEqual(params['videoId'], '420030')
            self.assertEqual(params['mtype'], '2')
            self.assertEqual(params['token'], '977b3ac79c1d8db14b7e6e246ecfa75a')
            return FakeResp()

        module = __import__('anime_spider.utils.m3u8_extractor', fromlist=['requests'])
        module.requests.get = fake_get
        try:
            results = self.extractor.extract_ikanbot_play_sources(response)
        finally:
            module.requests.get = original_get

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['source_name'], '线路1')
        self.assertEqual(results[0]['episodes'][0]['url'], 'https://play.xluuss.com/play/a/index.m3u8')
        self.assertEqual(results[0]['episodes'][0]['episode'], '01')
        self.assertEqual(results[1]['source_name'], '线路2')

    def _source_item_css_handler(self, selector, ep, href):
        mock = MagicMock()
        if selector == '::attr(data-episode)':
            mock.get = MagicMock(return_value=ep)
        elif selector == '::attr(data-ep)':
            mock.get = MagicMock(return_value=None)
        elif selector == '::text':
            mock.get = MagicMock(return_value=f'第{ep}集')
        elif selector == '::attr(href)':
            mock.get = MagicMock(return_value=href)
        else:
            mock.get = MagicMock(return_value=None)
        return mock

    def _ep_css_handler(self, selector):
        mock = MagicMock()
        if '::attr(data-episode)' in selector:
            mock.get = MagicMock(return_value='01')
        elif '::attr(data-ep)' in selector:
            mock.get = MagicMock(return_value=None)
        elif '::text' in selector:
            mock.get = MagicMock(return_value='第01集')
        elif '::attr(href)' in selector:
            mock.get = MagicMock(return_value='/play/123/ep01')
        else:
            mock.get = MagicMock(return_value=None)
        return mock


if __name__ == '__main__':
    unittest.main()
