"""测试动画内容检测模块"""

import unittest
from unittest.mock import MagicMock
from anime_spider.utils.anime_detector import AnimeDetector


class _SelectorList:
    def __init__(self, values=None, nodes=None):
        self.values = values or []
        self.nodes = nodes or []

    def get(self):
        return self.values[0] if self.values else None

    def getall(self):
        return self.values

    def __iter__(self):
        return iter(self.nodes)


class TestAnimeDetector(unittest.TestCase):
    """测试动画内容检测器"""

    def setUp(self):
        self.detector = AnimeDetector()

    def _mock_response(self, url='https://example.com/play/123', text='', css_map=None):
        """创建模拟的 Response 对象"""
        response = MagicMock()
        response.url = url
        response.text = text
        response.css = MagicMock(side_effect=lambda sel: self._css_handler(sel, css_map or {}))
        response.xpath = MagicMock(return_value=MagicMock(getall=MagicMock(return_value=[])))
        response.urljoin = MagicMock(side_effect=lambda value: value)
        return response

    def _css_handler(self, selector, css_map):
        """模拟 CSS 选择器"""
        if selector in css_map:
            value = css_map[selector]
            if isinstance(value, list):
                return _SelectorList(values=value)
            return _SelectorList(values=[value] if value else [])
        return _SelectorList()

    def test_detect_anime_page_by_url(self):
        """通过 URL 模式检测动漫页面"""
        response = self._mock_response(
            url='https://example.com/play/123',
            text='这是一个动漫播放页面',
        )
        result = self.detector.detect(response)
        self.assertIn('is_anime', result)
        self.assertIn('confidence', result)

    def test_detect_anime_page_by_keywords(self):
        """通过关键词检测动漫页面"""
        text = '动漫在线观看 新番动画 声优配音 高清720p'
        response = self._mock_response(
            url='https://example.com/video/123',
            text=text,
        )
        result = self.detector.detect(response)
        self.assertTrue(result['is_anime'])
        self.assertGreater(result['confidence'], 0.3)

    def test_detect_non_anime_page(self):
        """非动漫页面应返回低置信度"""
        text = '这是一个普通新闻页面，没有任何动漫相关内容'
        response = self._mock_response(
            url='https://example.com/news/123',
            text=text,
        )
        result = self.detector.detect(response)
        self.assertFalse(result['is_anime'])

    def test_detect_with_player_indicators(self):
        """包含播放器特征的页面"""
        text = '页面内容包含 dplayer 和 video 标签 <video src="test.m3u8">'
        response = self._mock_response(
            url='https://example.com/play/123',
            text=text,
        )
        result = self.detector.detect(response)
        self.assertGreater(result['confidence'], 0)

    def test_is_detail_page_with_url_pattern(self):
        """详情页 URL 模式判断"""
        response = self._mock_response(url='https://example.com/detail/12345')
        self.assertTrue(self.detector.is_detail_page(response))

    def test_is_not_detail_page(self):
        """非详情页判断"""
        response = self._mock_response(url='https://example.com/list')
        response.text = '普通列表页面'
        self.assertFalse(self.detector.is_detail_page(response))

    def test_extract_title(self):
        """提取标题"""
        response = self._mock_response(
            url='https://example.com/detail/123',
            text='页面内容',
            css_map={'h1::text': '鬼灭之刃 - 动漫详情'}
        )
        title = self.detector._extract_title(response)
        self.assertIsNotNone(title)

    def test_extract_year(self):
        """提取年份"""
        response = self._mock_response(
            url='https://example.com',
            text='年份：2019年 放送开始',
        )
        year = self.detector._extract_year(response)
        self.assertEqual(year, 2019)

    def test_extract_year_range(self):
        """年份范围验证"""
        response = self._mock_response(
            url='https://example.com',
            text='年份：1800年',  # 不合理的年份
        )
        year = self.detector._extract_year(response)
        self.assertIsNone(year)

    def test_extract_voice_actors(self):
        """提取声优列表"""
        response = self._mock_response(
            url='https://example.com',
            text='声优信息',
            css_map={'.actors a::text': ['花江夏树', '鬼头明里', '下野纮']},
        )
        actors = self.detector._extract_voice_actors(response)
        self.assertIsInstance(actors, list)

    def test_extract_poster(self):
        """提取海报图"""
        response = self._mock_response(
            url='https://example.com',
            text='',
            css_map={'.poster img::attr(src)': 'https://img.example.com/poster.jpg'},
        )
        poster = self.detector._extract_poster(response)
        self.assertIsNotNone(poster)

    def test_extract_douban_poster_uses_large_image_from_json_ld(self):
        """豆瓣 subject 页优先从 JSON-LD image 提取大图。"""
        response = self._mock_response(
            url='https://movie.douban.com/subject/37116612/',
            text='',
            css_map={
                'script[type="application/ld+json"]::text': (
                    '{"@type":"Movie","image":"https://img3.doubanio.com/view/photo/s_ratio_poster/public/p2930445903.jpg"}'
                ),
            },
        )
        poster = self.detector._extract_poster(response)
        self.assertEqual(
            poster,
            'https://img3.doubanio.com/view/photo/m/public/p2930445903.jpg',
        )

    def test_extract_douban_rating_from_json_ld(self):
        """豆瓣 subject 页应从 JSON-LD aggregateRating 提取评分。"""
        response = self._mock_response(
            url='https://movie.douban.com/subject/30215848/',
            text='',
            css_map={
                'script[type="application/ld+json"]::text': (
                    '{"@type":"TVSeries","aggregateRating":{"@type":"AggregateRating","ratingValue":"6.7","ratingCount":"12345"}}'
                ),
            },
        )
        metadata = self.detector.extract_metadata(response)
        self.assertEqual(metadata['douban_rating'], 6.7)

    def test_extract_genres(self):
        """提取类型标签"""
        response = self._mock_response(
            url='https://example.com',
            text='',
            css_map={'.genre a::text': ['动作', '奇幻', '冒险']},
        )
        genres = self.detector._extract_genres(response)
        self.assertIsInstance(genres, list)


if __name__ == '__main__':
    unittest.main()
