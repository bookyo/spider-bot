"""域名发现爬虫 - 自动发现新的动漫网站"""

import logging
from datetime import datetime

import scrapy

from anime_spider.items import DomainItem
from anime_spider.utils.domain_discover import DomainDiscover
from anime_spider.utils.db import MongoDB

logger = logging.getLogger(__name__)


class DiscoverSpider(scrapy.Spider):
    """域名发现爬虫

    通过证书透明度日志、DNS 枚举等方式自动发现动漫网站。
    发现后验证是否为动漫站点，存入数据库。
    """

    name = 'discover'
    allowed_domains = []

    def __init__(self, methods=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.methods = methods.split(',') if methods else ['crt_sh', 'dns_enum']
        self.discoverer = DomainDiscover()

    def start_requests(self):
        """启动发现流程"""
        logger.info(f'[Discover] 启动域名发现，方法: {self.methods}')

        # 运行域名发现
        domains = self.discoverer.discover_all(methods=self.methods)

        if not domains:
            logger.info('[Discover] 未发现新域名')
            return

        logger.info(f'[Discover] 发现 {len(domains)} 个域名，开始验证...')

        # 对每个发现的域名发起请求验证
        for domain in domains:
            # 检查是否已存在于数据库
            if self._is_domain_known(domain):
                logger.debug(f'[Discover] 域名已知，跳过: {domain}')
                continue

            url = f'https://{domain}'
            yield scrapy.Request(
                url=url,
                callback=self.parse_domain,
                errback=self.handle_error,
                meta={'domain': domain, 'handle_httpstatus_list': [403, 404, 500, 502, 503]},
                dont_filter=True,
                priority=10,
            )

    def parse_domain(self, response):
        """解析域名响应，判断是否为动漫站点"""
        domain = response.meta['domain']
        content = response.text.lower()

        # 检测动漫关键词
        from config.keywords import ANIME_SITE_KEYWORDS
        keyword_count = sum(1 for kw in ANIME_SITE_KEYWORDS if kw.lower() in content)

        is_anime_site = keyword_count >= 2

        if is_anime_site:
            logger.info(f'[Discover] 确认动漫站点: {domain} (关键词匹配: {keyword_count})')
        else:
            logger.debug(f'[Discover] 非动漫站点: {domain} (关键词匹配: {keyword_count})')
            return

        # 创建域名数据项
        item = DomainItem()
        item['domain'] = domain
        item['source'] = ','.join(self.methods)
        item['discovered_at'] = datetime.now().isoformat()
        item['is_anime_site'] = True
        item['last_crawled'] = None
        item['status'] = 'pending'

        yield item

    def handle_error(self, failure):
        """处理请求错误"""
        domain = failure.request.meta.get('domain', 'unknown')
        logger.debug(f'[Discover] 请求失败: {domain} - {failure.value}')

    def _is_domain_known(self, domain):
        """检查域名是否已存在于数据库"""
        try:
            col = MongoDB.get_domain_collection()
            return col.find_one({'domain': domain}) is not None
        except Exception as e:
            logger.warning(f'[Discover] 查询域名失败 {domain}: {e}')
            return False

    def closed(self, reason):
        """爬虫关闭时的清理"""
        logger.info(f'[Discover] 域名发现爬虫关闭，原因: {reason}')
