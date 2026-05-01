"""通用站点深度爬虫 - 爬取动漫网站并提取数据"""

import logging
from datetime import datetime
from urllib.parse import urlparse

import scrapy

from anime_spider.adapters import SiteAdapterRegistry
from anime_spider.items import AnimeItem, PlaySourceItem
from anime_spider.utils.anime_detector import AnimeDetector
from anime_spider.utils.crawl_metrics import CrawlMetrics
from anime_spider.utils.m3u8_extractor import M3U8Extractor
from anime_spider.utils.dedup import (
    generate_anime_dedup_key,
    generate_provider_id,
    generate_source_id,
    generate_title_aliases,
    normalize_title,
)
from anime_spider.utils.dedup import summarize_play_sources
from anime_spider.utils.db import MongoDB
from anime_spider.utils.domain_priority import DomainPriorityScorer
from anime_spider.utils.site_fingerprint import SiteFingerprint
from anime_spider.utils.url_features import URLFeatureAnalyzer
from anime_spider.utils.incremental_scheduler import IncrementalScheduler

logger = logging.getLogger(__name__)


class SiteSpider(scrapy.Spider):
    """通用动漫站点爬虫

    深度爬取动漫网站，提取动画数据和播放源。
    支持通过 -a domain=xxx.com 指定目标站点。
    """

    name = 'site'

    def __init__(self, domain=None, url=None, max_depth=3, incremental_mode=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_domain = domain
        self.start_url = url
        self.max_depth = int(max_depth)
        self.incremental_mode = str(incremental_mode).lower() in ('1', 'true', 'yes')
        self.detector = AnimeDetector()
        self.adapter_registry = SiteAdapterRegistry()
        self.m3u8_extractor = M3U8Extractor()
        self.fingerprint = SiteFingerprint()
        self.priority_scorer = DomainPriorityScorer()
        self.url_features = URLFeatureAnalyzer()
        self.incremental_scheduler = IncrementalScheduler()
        self.visited_urls = set()
        self.site_adapter = None
        self.extracted_anime_count = 0
        self.best_quality_score = None

        if not domain and not url:
            raise ValueError('必须指定 domain 或 url 参数')

    def start_requests(self):
        """生成起始请求"""
        if self.target_domain:
            try:
                adapter = self.adapter_registry.resolve_by_domain(self.target_domain)
                self.site_adapter = adapter
                MongoDB.update_domain_status(
                    self.target_domain,
                    'crawling',
                    last_crawled=datetime.now(),
                    site_type=adapter.name,
                    last_error=None,
                )
            except Exception as exc:
                logger.warning(f'[SiteSpider] 初始化域名状态失败 {self.target_domain}: {exc}')

        if self.start_url:
            urls = [self.start_url]
        elif self.target_domain:
            urls = [
                f'https://{self.target_domain}',
                f'http://{self.target_domain}',
            ]
        else:
            return

        for url in urls:
            yield scrapy.Request(
                url=url,
                callback=self.parse,
                meta={'depth': 0},
                dont_filter=True,
            )

    def parse(self, response):
        """解析页面"""
        url = response.url
        depth = response.meta.get('depth', 0)
        adapter = self.adapter_registry.resolve(response)
        self.site_adapter = self.site_adapter or adapter
        fingerprint = self.fingerprint.detect(response)
        url_features = self.url_features.analyze(response.url)

        # 防止重复访问
        if url in self.visited_urls:
            return
        self.visited_urls.add(url)

        # 超过最大深度
        if depth > self.max_depth:
            return

        # 检测是否为动画内容
        detection = adapter.detect(response, self.detector)
        detection['confidence'] = min(
            1.0,
            detection.get('confidence', 0.0) + url_features.get('score', 0.0)
        )

        if detection['is_anime']:
            logger.info(
                f'[SiteSpider] 发现动画页面: {url} '
                f'(置信度: {detection["confidence"]:.2f})'
            )

            # 如果是详情页，提取完整数据
            if adapter.is_detail_page(response, self.detector) or url_features.get('page_type') == 'detail':
                yield from self._extract_anime_data(response, detection, adapter, fingerprint)
            else:
                # 列表页，提取详情页链接
                yield from self._extract_detail_links(response, depth, adapter)

        # 播放页不继续扩散，否则会把每一集播放页都当成新的线路入口
        if not self.incremental_mode and url_features.get('page_type') != 'play':
            yield from self._follow_links(response, depth)

    def _extract_anime_data(self, response, detection, adapter, fingerprint):
        """从详情页提取动画完整数据"""
        metadata = adapter.extract_metadata(response, self.detector)

        # 提取 m3u8 播放源
        m3u8_links = self.m3u8_extractor.extract(response)
        grouped_play_sources = self.m3u8_extractor.extract_play_sources_from_page(response)
        if not grouped_play_sources:
            grouped_play_sources = self.m3u8_extractor.extract_ikanbot_play_sources(response)
        play_page_entries = self.m3u8_extractor.extract_play_page_entries(response)
        episodes = self.m3u8_extractor.extract_episodes_from_page(response)
        player_config = self.m3u8_extractor.extract_player_config(response)

        # 构建播放源
        play_sources = grouped_play_sources or self._build_play_sources(response, m3u8_links, episodes, player_config)
        episode_summary = summarize_play_sources(play_sources)

        # 创建动画数据项
        item = AnimeItem()
        item['title'] = metadata.get('title') or detection.get('title')
        item['original_title'] = metadata.get('title')
        item['year'] = metadata.get('year')
        item['director'] = metadata.get('director')
        item['voice_actors'] = metadata.get('voice_actors', [])
        item['synopsis'] = metadata.get('synopsis')
        item['poster_url'] = metadata.get('poster_url')
        item['source_url'] = response.url
        item['source_domain'] = urlparse(response.url).netloc
        item['genres'] = metadata.get('genres', [])
        item['play_sources'] = play_sources
        item['discovered_at'] = datetime.now().isoformat()
        item['extractor_name'] = adapter.name
        item['extractor_confidence'] = detection.get('confidence')
        item['site_type'] = fingerprint.get('site_type') or adapter.name
        item['normalized_title'] = normalize_title(item['title'])
        item['aliases'] = generate_title_aliases(item['title'], item['original_title'])
        item['latest_episode'] = episode_summary['latest_episode']
        item['total_episode_count'] = episode_summary['total_episode_count']
        item['new_episode_count'] = episode_summary['new_episode_count']
        item['incremental_found'] = episode_summary['new_episode_count'] > 0
        item['last_incremental_check'] = datetime.now()
        item['incremental_priority'] = self.incremental_scheduler.score(dict(item))

        # 生成去重键
        item['dedup_key'] = generate_anime_dedup_key(
            item['title'], item['year'], item['director']
        )

        # 只有标题存在时才保存
        if item['title']:
            self.extracted_anime_count += 1
            if item.get('quality_score') is not None:
                if self.best_quality_score is None:
                    self.best_quality_score = item.get('quality_score')
                else:
                    self.best_quality_score = max(self.best_quality_score, item.get('quality_score'))
            yield item
        else:
            logger.debug(f'[SiteSpider] 页面缺少标题，跳过: {response.url}')

        for entry_group in play_page_entries:
            for entry in entry_group.get('entries', []):
                play_page_url = entry.get('play_page_url')
                if not play_page_url:
                    continue
                yield scrapy.Request(
                    url=play_page_url,
                    callback=self._parse_play_page,
                    meta={
                        'anime_title': item['title'],
                        'anime_dedup_key': item['dedup_key'],
                        'anime_key': entry_group.get('anime_key'),
                        'source_name': entry_group.get('source_name'),
                        'episode': entry.get('episode'),
                        'source_url': response.url,
                        'depth': response.meta.get('depth', 0) + 1,
                    },
                    priority=10,
                )

        # 如果有 iframe 播放器，需要进一步请求
        for link in m3u8_links:
            if link.get('needs_follow'):
                yield scrapy.Request(
                    url=link['url'],
                    callback=self._parse_player_iframe,
                    meta={
                        'anime_title': item['title'],
                        'anime_dedup_key': item['dedup_key'],
                        'depth': response.meta.get('depth', 0) + 1,
                    },
                    priority=5,
                )

    def _parse_play_page(self, response):
        """从播放页提取最终媒体链接并回写为真实播放源。"""
        player_config = self.m3u8_extractor.extract_player_config(response)
        media_url = player_config.get('url')
        if not media_url or not self.m3u8_extractor._is_playable_media_url(media_url):
            m3u8_links = self.m3u8_extractor.extract(response)
            media_candidates = [link for link in m3u8_links if link.get('url') and not link.get('needs_follow')]
            media_url = media_candidates[0]['url'] if media_candidates else None

        if not media_url:
            return

        source_name = response.meta.get('source_name') or player_config.get('from') or 'play'
        source = {
            'domain': urlparse(response.url).netloc,
            'source_name': source_name,
            'episodes': [{
                'episode': response.meta.get('episode'),
                'url': media_url,
            }],
            'quality': None,
            'raw_url': response.url,
        }

        anime_key = response.meta.get('anime_key') or self.m3u8_extractor._extract_anime_play_key(response.url)
        if anime_key:
            source['anime_key'] = anime_key
        if player_config.get('from'):
            source['line_from'] = str(player_config['from'])
        if player_config.get('sid') is not None:
            source['line_sid'] = str(player_config['sid'])
        line_parts = [
            str(part).strip()
            for part in [player_config.get('from'), player_config.get('sid'), source_name]
            if part not in (None, '')
        ]
        if line_parts:
            source['line_id'] = '|'.join(line_parts)
        if player_config.get('url'):
            source['provider_key'] = urlparse(player_config['url']).netloc.lower()

        source['provider_id'] = generate_provider_id(source)
        source['source_id'] = generate_source_id(source)

        item = AnimeItem()
        item['dedup_key'] = response.meta.get('anime_dedup_key')
        item['title'] = None
        item['play_sources'] = [source]
        item['source_url'] = response.meta.get('source_url') or response.url
        item['source_domain'] = urlparse(response.url).netloc
        item['discovered_at'] = datetime.now().isoformat()
        item['extractor_name'] = 'play_page_follow'
        item['site_type'] = 'play_page_follow'
        item['aliases'] = []
        item['normalized_title'] = None
        item['latest_episode'] = None
        item['total_episode_count'] = 0
        item['new_episode_count'] = 0
        item['incremental_found'] = False
        item['last_incremental_check'] = datetime.now()
        item['incremental_priority'] = 0.0
        yield item

    def _parse_player_iframe(self, response):
        """解析播放器 iframe 页面，通过 pipeline 更新播放源"""
        m3u8_links = self.m3u8_extractor.extract(response)

        if m3u8_links:
            play_source = {
                'domain': urlparse(response.url).netloc,
                'source_name': 'iframe',
                'episodes': [],
                'quality': None,
                'raw_url': response.url,
            }

            for link in m3u8_links:
                if link.get('url') and not link.get('needs_follow'):
                    play_source['episodes'].append({
                        'episode': link.get('episode'),
                        'url': link['url'],
                    })

            if play_source['episodes']:
                play_source['provider_id'] = generate_provider_id(play_source)
                play_source['source_id'] = generate_source_id(play_source)
                # 通过 pipeline 更新，而非直接写 DB
                item = AnimeItem()
                item['dedup_key'] = response.meta.get('anime_dedup_key')
                item['title'] = None
                item['play_sources'] = [play_source]
                item['source_url'] = response.url
                item['source_domain'] = urlparse(response.url).netloc
                item['discovered_at'] = datetime.now().isoformat()
                item['extractor_name'] = 'iframe_follow'
                item['site_type'] = 'iframe_follow'
                item['aliases'] = []
                item['normalized_title'] = None
                item['latest_episode'] = None
                item['total_episode_count'] = 0
                item['new_episode_count'] = 0
                item['incremental_found'] = False
                item['last_incremental_check'] = datetime.now()
                item['incremental_priority'] = 0.0
                yield item

    def _extract_detail_links(self, response, depth, adapter):
        """从列表页提取详情页链接"""
        for link in adapter.extract_detail_links(response):
            url = response.urljoin(link)
            if url not in self.visited_urls:
                yield scrapy.Request(
                    url=url,
                    callback=self.parse,
                    meta={'depth': depth + 1},
                    priority=5,
                )

    def _follow_links(self, response, depth):
        """跟随页面中的链接继续爬取"""
        if depth >= self.max_depth:
            return

        # 提取所有链接
        links = response.css('a::attr(href)').getall()

        for link in links:
            if not link:
                continue

            url = response.urljoin(link)
            parsed = urlparse(url)

            # 只爬取同域名的链接
            if parsed.netloc and parsed.netloc != urlparse(response.url).netloc:
                continue

            # 跳过锚点和 javascript
            if url.startswith('#') or url.startswith('javascript:'):
                continue

            # 跳过非 HTTP 链接
            if not url.startswith('http'):
                continue

            # 跳过资源文件
            if any(url.lower().endswith(ext) for ext in [
                '.jpg', '.jpeg', '.png', '.gif', '.css', '.js',
                '.ico', '.svg', '.woff', '.woff2', '.ttf',
                '.mp4', '.mp3', '.pdf', '.zip',
            ]):
                continue

            if url not in self.visited_urls:
                yield scrapy.Request(
                    url=url,
                    callback=self.parse,
                    meta={'depth': depth + 1},
                    priority=1,
                )

    def _build_play_sources(self, response, m3u8_links, episodes, player_config=None):
        """构建播放源列表"""
        sources = []
        player_config = player_config or {}

        # 按域名分组
        domain_episodes = {}

        # 处理直接提取的 m3u8 链接
        for link in m3u8_links:
            if link.get('needs_follow'):
                continue

            link_domain = urlparse(link['url']).netloc
            if link_domain not in domain_episodes:
                domain_episodes[link_domain] = []
            domain_episodes[link_domain].append({
                'episode': link.get('episode'),
                'url': link['url'],
            })

        # 构建播放源对象
        for domain_name, episodes_list in domain_episodes.items():
            if episodes_list:
                provider_key = None
                if player_config.get('url'):
                    provider_key = urlparse(player_config['url']).netloc.lower()

                source_name = (
                    player_config.get('from') or
                    domain_name
                )
                source = {
                    'domain': domain_name,
                    'source_name': source_name,
                    'episodes': episodes_list,
                    'quality': None,
                    'raw_url': response.url,
                }
                anime_key_match = self.m3u8_extractor._extract_anime_play_key(response.url)
                if anime_key_match:
                    source['anime_key'] = anime_key_match
                if provider_key:
                    source['provider_key'] = provider_key
                if player_config.get('from'):
                    source['line_from'] = str(player_config['from'])
                if player_config.get('sid') is not None:
                    source['line_sid'] = str(player_config['sid'])
                line_parts = [
                    str(part).strip()
                    for part in [player_config.get('from'), player_config.get('sid'), source_name]
                    if part not in (None, '')
                ]
                if line_parts:
                    source['line_id'] = '|'.join(line_parts)
                source['provider_id'] = generate_provider_id(source)
                source['source_id'] = generate_source_id(source)
                sources.append(source)

        return sources

    def closed(self, reason):
        """爬虫关闭时的清理"""
        domain = self.target_domain
        if domain:
            status = 'completed' if reason == 'finished' else 'failed'
            existing = MongoDB.get_domain(domain)
            metrics = CrawlMetrics.build_domain_update(
                existing,
                crawl_succeeded=(reason == 'finished'),
                quality_score=self.best_quality_score,
                anime_count_delta=self.extracted_anime_count,
            )
            priority_score = self.priority_scorer.score({
                **(existing or {}),
                **metrics,
                'status': status,
                'last_crawled': datetime.now(),
            })
            extra = {
                'last_crawled': datetime.now(),
                'site_type': self.site_adapter.name if self.site_adapter else None,
                'priority_score': priority_score,
                **metrics,
            }
            if reason != 'finished':
                extra['last_error'] = reason
            try:
                MongoDB.update_domain_status(domain, status, **extra)
            except Exception as exc:
                logger.warning(f'[SiteSpider] 更新域名状态失败 {domain}: {exc}')

        logger.info(f'[SiteSpider] 站点爬虫关闭，原因: {reason}')
        logger.info(f'[SiteSpider] 共访问 {len(self.visited_urls)} 个页面')
