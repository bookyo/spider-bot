"""Scrapy 中间件 - UA 轮换、重试等"""

from datetime import datetime
import random
import logging
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.project import get_project_settings
from anime_spider.utils.db import MongoDB

logger = logging.getLogger(__name__)


class ProxyMiddleware:
    """为爬虫请求统一注入可选代理。"""

    def __init__(self, proxy_url=None):
        self.proxy_url = str(proxy_url or '').strip()

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings.get('CRAWLER_PROXY_URL'))

    def process_request(self, request, spider):
        if self.proxy_url and 'proxy' not in request.meta:
            request.meta['proxy'] = self.proxy_url
        return None


class RandomUserAgentMiddleware:
    """随机 User-Agent 中间件"""

    def __init__(self):
        settings = get_project_settings()
        self.user_agent_list = settings.get('USER_AGENT_LIST', [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ])

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def process_request(self, request, spider):
        ua = random.choice(self.user_agent_list)
        request.headers['User-Agent'] = ua
        return None


class RetryMiddleware(RetryMiddleware):
    """增强的重试中间件"""

    def _mark_retry(self, request, spider, reason):
        domain = getattr(spider, 'target_domain', None)
        if not domain:
            return

        retry_count = request.meta.get('retry_times', 0) + 1
        try:
            MongoDB.update_domain_status(
                domain,
                'crawling',
                retry_count=retry_count,
                last_error=str(reason),
                last_crawled=datetime.now(),
            )
        except Exception as exc:
            logger.debug(f'[Retry] 更新重试状态失败 {domain}: {exc}')

    def process_response(self, request, response, spider):
        # 对于 403/429 等状态码，等待后重试
        if response.status in [403, 429, 500, 502, 503, 504]:
            logger.warning(f'[Retry] 收到 {response.status}，等待重试: {request.url}')
            self._mark_retry(request, spider, response.status)
            return self._retry(request, response.status, spider) or response

        return super().process_response(request, response, spider)

    def process_exception(self, request, exception, spider):
        self._mark_retry(request, spider, exception)
        return super().process_exception(request, exception, spider)
