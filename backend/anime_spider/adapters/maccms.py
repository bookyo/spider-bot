"""MacCMS 站型适配器。"""

from anime_spider.adapters.base import BaseSiteAdapter


class MacCMSAdapter(BaseSiteAdapter):
    """适配常见 MacCMS / STUI 模板。"""

    name = 'maccms'
    priority = 80

    DETAIL_SELECTORS = [
        '.vod-detail',
        '.stui-content__detail',
        '.stui-content__thumb',
    ]

    DETAIL_LINK_SELECTORS = [
        '.stui-vodlist a::attr(href)',
        '.stui-content__playlist a::attr(href)',
    ]

    def matches(self, response):
        content = response.text.lower()
        return (
            'stui-vodlist' in content or
            'stui-content__playlist' in content or
            'mac_url' in content
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
