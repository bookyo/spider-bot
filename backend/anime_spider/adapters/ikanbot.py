"""v.ikanbot.com 站点适配器。"""

from anime_spider.adapters.base import BaseSiteAdapter


class IkanbotAdapter(BaseSiteAdapter):
    """适配 ikanbot 详情页的 .detail .meta 结构。"""

    name = 'ikanbot'
    priority = 120

    def matches(self, response):
        return self.normalize_domain(response) == 'v.ikanbot.com'

    def is_detail_page(self, response, detector):
        if response.css('.detail .meta.title::text').get():
            return True
        return detector.is_detail_page(response)

    def extract_detail_links(self, response):
        links = []
        seen = set()
        for href in response.css('a::attr(href)').getall():
            if not href or '/play/' not in href:
                continue
            url = response.urljoin(href)
            if url in seen:
                continue
            seen.add(url)
            links.append(url)
        return links

    def extract_metadata(self, response, detector):
        metadata = detector.extract_metadata(response)

        title = response.css('.detail .meta.title::text').get()
        if title and title.strip():
            metadata['title'] = title.strip()

        meta_values = [
            value.strip()
            for value in response.css('.detail h3.meta::text').getall()
            if value and value.strip()
        ]

        # 当前结构:
        # 0: 原名/别名
        # 1: 年份
        # 2: 地区
        # 3: 导演/主演
        if len(meta_values) >= 1 and meta_values[0]:
            metadata['original_title'] = meta_values[0]

        if len(meta_values) >= 2:
            year = detector._parse_year_value(meta_values[1])
            if year is not None:
                metadata['year'] = year

        if len(meta_values) >= 4 and meta_values[3]:
            people = [part.strip() for part in meta_values[3].split('/') if part.strip()]
            if people:
                metadata['director'] = people[0]
                actors_text = '/'.join(people[1:])
                actors = detector._split_people_text(actors_text)
                if actors:
                    metadata['voice_actors'] = actors

        return metadata
