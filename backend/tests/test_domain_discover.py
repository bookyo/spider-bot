"""测试域名发现模块"""

import unittest
from unittest.mock import patch, MagicMock
from anime_spider.utils.domain_discover import DomainDiscover


class TestDomainDiscover(unittest.TestCase):
    """测试域名发现器"""

    def setUp(self):
        self.discoverer = DomainDiscover()

    def test_is_valid_domain_valid(self):
        """有效域名验证"""
        self.assertTrue(self.discoverer._is_valid_domain('example.com'))
        self.assertTrue(self.discoverer._is_valid_domain('anime.example.com'))
        self.assertTrue(self.discoverer._is_valid_domain('test-site.org'))

    def test_is_valid_domain_invalid(self):
        """无效域名验证"""
        self.assertFalse(self.discoverer._is_valid_domain(''))
        self.assertFalse(self.discoverer._is_valid_domain('192.168.1.1'))  # IP
        self.assertFalse(self.discoverer._is_valid_domain('.example.com'))  # 以点开头
        self.assertFalse(self.discoverer._is_valid_domain('a' * 300))  # 过长

    def test_is_valid_domain_excluded(self):
        """排除域名验证"""
        self.assertFalse(self.discoverer._is_valid_domain('google.com'))
        self.assertFalse(self.discoverer._is_valid_domain('youtube.com'))
        self.assertFalse(self.discoverer._is_valid_domain('api.googleapis.com'))

    def test_filter_domains(self):
        """域名过滤"""
        domains = {
            'example.com',
            'google.com',      # 应被排除
            '192.168.1.1',     # 应被排除
            'anime-site.org',
            '',                # 应被排除
        }
        filtered = self.discoverer._filter_domains(domains)
        self.assertIn('example.com', filtered)
        self.assertIn('anime-site.org', filtered)
        self.assertNotIn('google.com', filtered)
        self.assertNotIn('192.168.1.1', filtered)
        self.assertNotIn('', filtered)

    @patch('anime_spider.utils.domain_discover.requests.get')
    def test_discover_from_crt_sh(self, mock_get):
        """测试 crt.sh 域名发现"""
        # 模拟 crt.sh 响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'name_value': 'anime-example.com'},
            {'name_value': 'www.anime-example.com'},
            {'name_value': 'dongman-site.org\nwww.dongman-site.org'},
        ]
        mock_get.return_value = mock_response

        domains = self.discoverer.discover_from_crt_sh()
        self.assertIsInstance(domains, set)
        # 应该包含解析出的域名
        self.assertTrue(len(domains) > 0)

    @patch('anime_spider.utils.domain_discover.requests.get')
    def test_discover_from_crt_sh_error(self, mock_get):
        """crt.sh 请求失败时应返回空集合"""
        mock_get.side_effect = Exception('Network error')
        domains = self.discoverer.discover_from_crt_sh()
        self.assertEqual(len(domains), 0)

    @patch('anime_spider.utils.domain_discover.dns.resolver.resolve')
    def test_discover_from_dns_enum(self, mock_resolve):
        """测试 DNS 枚举"""
        # 模拟 DNS 解析成功
        mock_resolve.return_value = ['1.2.3.4']

        domains = self.discoverer.discover_from_dns_enum(base_domains=['example.com'])
        self.assertIsInstance(domains, set)
        # 应该发现一些子域名
        self.assertTrue(len(domains) > 0)

    @patch('anime_spider.utils.domain_discover.dns.resolver.resolve')
    def test_discover_from_dns_enum_no_results(self, mock_resolve):
        """DNS 枚举无结果"""
        import dns.resolver
        mock_resolve.side_effect = dns.resolver.NXDOMAIN()

        domains = self.discoverer.discover_from_dns_enum(base_domains=['nonexistent.com'])
        self.assertEqual(len(domains), 0)

    @patch('anime_spider.utils.domain_discover.requests.get')
    def test_verify_anime_site_positive(self, mock_get):
        """验证动漫站点 - 正面"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '动漫在线观看 新番动画 高清播放 anime'
        mock_get.return_value = mock_response

        result = self.discoverer.verify_anime_site('anime-example.com')
        self.assertTrue(result)

    @patch('anime_spider.utils.domain_discover.requests.get')
    def test_verify_anime_site_negative(self, mock_get):
        """验证动漫站点 - 负面"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '这是一个普通的新闻网站，没有任何动漫相关内容'
        mock_get.return_value = mock_response

        result = self.discoverer.verify_anime_site('news-site.com')
        self.assertFalse(result)

    @patch('anime_spider.utils.domain_discover.requests.get')
    def test_verify_anime_site_network_error(self, mock_get):
        """验证动漫站点 - 网络错误"""
        mock_get.side_effect = Exception('Connection refused')
        result = self.discoverer.verify_anime_site('down-site.com')
        self.assertFalse(result)

    def test_discover_all_with_methods(self):
        """测试综合发现流程"""
        with patch.object(self.discoverer, 'discover_from_crt_sh', return_value={'a.com'}):
            with patch.object(self.discoverer, 'discover_from_dns_enum', return_value={'b.com'}):
                domains = self.discoverer.discover_all(methods=['crt_sh', 'dns_enum'])
                self.assertIsInstance(domains, set)


if __name__ == '__main__':
    unittest.main()
