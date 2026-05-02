"""MacCMS 站型适配器。"""

import re

from anime_spider.adapters.base import BaseSiteAdapter


class MacCMSAdapter(BaseSiteAdapter):
    """适配常见 MacCMS / STUI 模板。"""

    name = 'maccms'
    priority = 80

    DETAIL_SELECTORS = [
        '.vod-detail',
        '.stui-content__detail',
        '.stui-content__thumb',
        '.ewave-player__detail',
        '.ewave-vodlist__thumb',
        'a[href*="/vodplay/"]',
        'a[href*="/vod/play/"]',
    ]

    DETAIL_LINK_SELECTORS = [
        '.stui-vodlist a::attr(href)',
        '.stui-content__playlist a::attr(href)',
        '.ewave-vodlist__bd a::attr(href)',
        '.ewave-vodlist__text a::attr(href)',
        'a.thumb-link::attr(href)',
        'a[href*="/voddetail/"]::attr(href)',
        'a[href*="/vod/detail/"]::attr(href)',
    ]

    def matches(self, response):
        content = response.text.lower()
        return (
            'stui-vodlist' in content or
            'stui-content__playlist' in content or
            'mac_url' in content or
            'ewave-vodlist' in content or
            'ewave-content__playlist' in content or
            '/voddetail/' in content or
            '/vodplay/' in content or
            '/vod/detail/' in content or
            '/vod/play/' in content
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
                if not link or ('/voddetail/' not in link and '/vod/detail/' not in link):
                    continue
                normalized = response.urljoin(link)
                if normalized not in seen:
                    seen.add(normalized)
                    links.append(normalized)
        return links

    def extract_metadata(self, response, detector):
        metadata = detector.extract_metadata(response)

        title = (
            response.css('.vod-detail h1 *::text').get() or
            response.css('.vod-detail h1::text').get() or
            response.css('h1.title span::text').get() or
            response.css('h1.title a::text').get() or
            response.css('h1 *::text').get() or
            response.css('h1::text').get() or
            response.css('.ewave-player__detail .title span::text').get() or
            response.css('.ewave-vodlist__thumb::attr(title)').get()
        )
        if title:
            cleaned = str(title).strip()
            cleaned = re.sub(r'[:：].*$', '', cleaned).strip()
            if cleaned:
                metadata['title'] = cleaned

        poster = (
            response.css('.ewave-content__thumb .ewave-vodlist__thumb img::attr(data-original)').get() or
            response.css('.ewave-content__thumb .ewave-vodlist__thumb::attr(data-original)').get() or
            response.css('.ewave-content__thumb .ewave-vodlist__thumb::attr(style)').re_first(r'url\\((.*?)\\)') or
            response.css('.stui-content__thumb img::attr(data-original)').get() or
            response.css('.vod-detail img::attr(data-src)').get() or
            response.css('.vod-detail img::attr(data-original)').get() or
            response.css('.ewave-content__thumb .ewave-vodlist__thumb img::attr(src)').get() or
            response.css('.stui-content__thumb img::attr(src)').get()
        )
        if poster:
            metadata['poster_url'] = response.urljoin(str(poster).strip(' "\''))

        text = ' '.join(part.strip() for part in response.css('body ::text').getall() if part.strip())
        year_match = re.search(r'年份\D{0,20}((?:19|20)\d{2})', text)
        if not year_match:
            year_match = re.search(r'上映于\D{0,20}((?:19|20)\d{2})', text)
        if year_match:
            metadata['year'] = int(year_match.group(1))

        desc_parts = response.css('#desc p::text, #desc p *::text').getall()
        desc = ' '.join(part.strip() for part in desc_parts if part and part.strip())
        if not desc:
            detail_text = ' '.join(part.strip() for part in response.css('.vod-detail ::text').getall() if part.strip())
            desc_match = re.search(r'简介[：:]\s*(.+?)(?:详细|主演[：:]|导演[：:]|更新[：:]|立即播放|$)', detail_text)
            if desc_match:
                desc = desc_match.group(1).strip()
        if desc:
            desc = re.sub(r'^.*?剧情简介[：:]', '', desc).strip()
            metadata['synopsis'] = desc[:2000]

        actor_match = re.search(r'由(.+?)等主演', text)
        if actor_match:
            actor_text = actor_match.group(1).replace('}', ' ')
            actors = [part.strip() for part in re.split(r'\s+|/|、|,|，', actor_text) if part.strip()]
            if actors:
                metadata['voice_actors'] = actors[:20]

        return metadata
