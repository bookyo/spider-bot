"""模块化主题站点适配器。"""

from anime_spider.adapters.base import BaseSiteAdapter


class ModuleThemeAdapter(BaseSiteAdapter):
    """适配常见 module-* 结构站点。"""

    name = 'module-theme'
    priority = 70

    DETAIL_SELECTORS = [
        '.module-info',
        '.module-play-list',
        '.module-info-heading',
    ]

    DETAIL_LINK_SELECTORS = [
        '.module-item a::attr(href)',
        '.module-items a::attr(href)',
        'a.module-play-list-link::attr(href)',
    ]

    def matches(self, response):
        content = response.text.lower()
        return (
            'module-item' in content or
            'module-info' in content or
            'module-play-list' in content
        )

    def is_detail_page(self, response, detector):
        for selector in self.DETAIL_SELECTORS:
            if response.css(selector).get():
                return True
        return detector.is_detail_page(response)

    def extract_detail_links(self, response):
        links = []
        seen = set()
        for selector in self.DETAIL_LINK_SELECTORS:
            for link in response.css(selector).getall():
                if link and link not in seen:
                    seen.add(link)
                    links.append(link)
        return links
