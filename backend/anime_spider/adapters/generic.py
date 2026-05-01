"""通用站点适配器。"""

from anime_spider.adapters.base import BaseSiteAdapter


class GenericSiteAdapter(BaseSiteAdapter):
    """通用回退适配器。"""

    name = 'generic'
    priority = -100

    DETAIL_SELECTORS = [
        'a[href*="/detail/"]::attr(href)',
        'a[href*="/anime/"]::attr(href)',
        'a[href*="/video/"]::attr(href)',
        'a[href*="/vod/"]::attr(href)',
        'a[href*="/bangumi/"]::attr(href)',
        'a[href*="/post/"]::attr(href)',
        'a[href*="/article/"]::attr(href)',
        'a[href*="/archives/"]::attr(href)',
        '.module-item a::attr(href)',
        '.module-items a::attr(href)',
        '.stui-vodlist a::attr(href)',
        '.video-item a::attr(href)',
        '.anime-item a::attr(href)',
        '.list-item a::attr(href)',
    ]

    def matches(self, response):
        return True

    def extract_detail_links(self, response):
        links = []
        seen = set()

        for selector in self.DETAIL_SELECTORS:
            for link in response.css(selector).getall():
                if link and link not in seen:
                    seen.add(link)
                    links.append(link)

        return links
