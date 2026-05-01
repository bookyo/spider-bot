"""站点适配器注册中心。"""

from urllib.parse import urlparse

from anime_spider.adapters.base import BaseSiteAdapter
from anime_spider.adapters.generic import GenericSiteAdapter
from anime_spider.adapters.maccms import MacCMSAdapter
from anime_spider.adapters.module_theme import ModuleThemeAdapter
from anime_spider.adapters.video_info import VideoInfoThemeAdapter
from anime_spider.utils.site_fingerprint import SiteFingerprint
from config.sites import SITE_RULES


class RuleBasedSiteAdapter(BaseSiteAdapter):
    """基于站点配置的选择器适配器。"""

    name = 'rule_based'
    priority = 100

    def __init__(self, domain, rule):
        self.domain = domain
        self.rule = rule or {}

    def matches(self, response):
        page_domain = urlparse(response.url).netloc.lower()
        return page_domain == self.domain or page_domain.endswith(f'.{self.domain}')

    def is_detail_page(self, response, detector):
        detail_selector = self.rule.get('detail_selector')
        if detail_selector and response.css(detail_selector).get():
            return True
        return detector.is_detail_page(response)

    def extract_metadata(self, response, detector):
        metadata = detector.extract_metadata(response)

        mapping = {
            'title': self.rule.get('title'),
            'director': self.rule.get('director'),
            'synopsis': self.rule.get('synopsis'),
            'poster_url': self.rule.get('poster'),
        }

        for field, selector in mapping.items():
            if selector:
                value = response.css(selector).get()
                if value:
                    metadata[field] = response.urljoin(value.strip()) if field == 'poster_url' else value.strip()

        voice_selector = self.rule.get('voice_actors')
        if voice_selector:
            actors = [item.strip() for item in response.css(voice_selector).getall() if item and item.strip()]
            if actors:
                metadata['voice_actors'] = actors

        genre_selector = self.rule.get('genres')
        if genre_selector:
            genres = [item.strip() for item in response.css(genre_selector).getall() if item and item.strip()]
            if genres:
                metadata['genres'] = genres

        return metadata

    def extract_detail_links(self, response):
        selector = self.rule.get('detail_links') or self.rule.get('episode_list')
        if not selector:
            return []
        return [link for link in response.css(selector).getall() if link]


class SiteAdapterRegistry:
    """根据域名和页面特征选择适配器。"""

    def __init__(self):
        self._fingerprint = SiteFingerprint()
        self._rule_adapters = [
            RuleBasedSiteAdapter(domain, rule)
            for domain, rule in SITE_RULES.items()
        ]
        self._builtin_adapters = [
            MacCMSAdapter(),
            ModuleThemeAdapter(),
            VideoInfoThemeAdapter(),
        ]
        self._fallback = GenericSiteAdapter()

    def resolve(self, response):
        for adapter in sorted(self._rule_adapters, key=lambda item: item.priority, reverse=True):
            if adapter.matches(response):
                return adapter
        for adapter in sorted(self._builtin_adapters, key=lambda item: item.priority, reverse=True):
            if adapter.matches(response):
                return adapter

        fingerprint = self._fingerprint.detect(response)
        if fingerprint['site_type'] == 'maccms':
            return MacCMSAdapter()
        if fingerprint['site_type'] == 'module-theme':
            return ModuleThemeAdapter()
        if fingerprint['site_type'] == 'video-info-theme':
            return VideoInfoThemeAdapter()
        return self._fallback

    def resolve_by_domain(self, domain):
        normalized = (domain or '').lower()
        for adapter in self._rule_adapters:
            if normalized == adapter.domain or normalized.endswith(f'.{adapter.domain}'):
                return adapter
        return self._fallback
