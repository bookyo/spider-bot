"""测试站点适配器分派。"""

import unittest
from unittest.mock import MagicMock

from anime_spider.adapters.maccms import MacCMSAdapter
from anime_spider.adapters.module_theme import ModuleThemeAdapter
from anime_spider.adapters.registry import SiteAdapterRegistry
from anime_spider.adapters.video_info import VideoInfoThemeAdapter


class TestSiteAdapterRegistry(unittest.TestCase):
    """测试站点适配器注册中心。"""

    def setUp(self):
        self.registry = SiteAdapterRegistry()

    def _mock_response(self, url):
        response = MagicMock()
        response.url = url
        response.css = MagicMock(return_value=MagicMock(get=MagicMock(return_value=None), getall=MagicMock(return_value=[])))
        return response

    def test_resolve_generic_when_no_rule_matches(self):
        response = self._mock_response('https://unknown-anime.example/detail/1')
        adapter = self.registry.resolve(response)
        self.assertEqual(adapter.name, 'generic')

    def test_resolve_by_domain_returns_generic_when_missing(self):
        adapter = self.registry.resolve_by_domain('unknown-anime.example')
        self.assertEqual(adapter.name, 'generic')

    def test_resolve_maccms_by_fingerprint(self):
        response = self._mock_response('https://video.example/vod/1')
        response.text = '<div class="stui-vodlist"></div><div class="stui-content__playlist"></div>'
        adapter = self.registry.resolve(response)
        self.assertIsInstance(adapter, MacCMSAdapter)

    def test_resolve_module_theme(self):
        response = self._mock_response('https://video.example/a/1')
        response.text = '<div class="module-item"></div><div class="module-info"></div>'
        adapter = self.registry.resolve(response)
        self.assertIsInstance(adapter, ModuleThemeAdapter)

    def test_resolve_video_info_theme(self):
        response = self._mock_response('https://video.example/a/1')
        response.text = '<div class="video-info-items"></div><div class="scroll-content"></div>'
        adapter = self.registry.resolve(response)
        self.assertIsInstance(adapter, VideoInfoThemeAdapter)


if __name__ == '__main__':
    unittest.main()
