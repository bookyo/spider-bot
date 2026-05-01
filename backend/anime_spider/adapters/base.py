"""站点适配器基类。"""

from urllib.parse import urlparse


class BaseSiteAdapter:
    """站点适配器基类。"""

    name = 'base'
    priority = 0

    def matches(self, response):
        """判断适配器是否匹配当前页面。"""
        return False

    def detect(self, response, detector):
        """检测页面是否为动漫内容。"""
        return detector.detect(response)

    def is_detail_page(self, response, detector):
        """判断是否为详情页。"""
        return detector.is_detail_page(response)

    def extract_metadata(self, response, detector):
        """提取详情页元数据。"""
        return detector.extract_metadata(response)

    def extract_detail_links(self, response):
        """提取详情链接。"""
        return []

    def normalize_domain(self, response):
        """返回当前页面域名。"""
        return urlparse(response.url).netloc.lower()
