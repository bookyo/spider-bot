"""video-info 主题站点适配器。"""

from anime_spider.adapters.base import BaseSiteAdapter


class VideoInfoThemeAdapter(BaseSiteAdapter):
    """适配 video-info-* 结构站点。"""

    name = 'video-info-theme'
    priority = 60

    DETAIL_SELECTORS = [
        '.video-info-items',
        '.video-info-aux',
        '.scroll-content',
    ]

    DETAIL_LINK_SELECTORS = [
        '.video-item a::attr(href)',
        '.list-item a::attr(href)',
        '.scroll-content a::attr(href)',
    ]

    def matches(self, response):
        content = response.text.lower()
        return (
            'video-info-items' in content or
            'video-info-aux' in content or
            'scroll-content' in content
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
