import os

from config.env import load_backend_env

load_backend_env()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BOT_NAME = 'anime_spider'
SPIDER_MODULES = ['anime_spider.spiders']
NEWSPIDER_MODULE = 'anime_spider.spiders'

# Robots.txt
ROBOTSTXT_OBEY = False

# 并发和限速
CONCURRENT_REQUESTS = 8
DOWNLOAD_DELAY = 2
RANDOMIZE_DOWNLOAD_DELAY = True
CONCURRENT_REQUESTS_PER_DOMAIN = 4

# 超时设置
DOWNLOAD_TIMEOUT = 30
RETRY_TIMES = 3

# 日志级别
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

# MongoDB 配置
MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017')
MONGODB_DB = os.environ.get('MONGODB_DB', 'anime_db')
MONGODB_ANIME_COLLECTION = os.environ.get('MONGODB_ANIME_COLLECTION', 'anime')
MONGODB_DOMAIN_COLLECTION = os.environ.get('MONGODB_DOMAIN_COLLECTION', 'discovered_domains')

# 域名发现配置
DISCOVERY_METHODS = ['crt_sh', 'whois', 'dns_enum']
CRT_SH_QUERIES = [
    '%anime%', '%dongman%', '%acg%',
    '%donghua%', '%bangumi%', '%dm%',
]
WHOIS_KEYWORDS = [
    'anime', 'dongman', 'acg', 'dm',
    'bangumi', 'donghua', 'anim',
]
DNS_ENUM_PREFIXES = [
    'www', 'm', 'api', 'video', 'play',
    'cdn', 'v2', 'new', 'app', 'tv', 'bbs',
]

# 爬取深度限制
MAX_DEPTH = int(os.environ.get('MAX_DEPTH', '3') or 3)
CRAWLER_PROXY_URL = os.environ.get('CRAWLER_PROXY_URL', '').strip()

# 海报配置
POSTER_DIR = os.environ.get('POSTER_DIR', os.path.join(BASE_DIR, 'posters'))
POSTER_MIN_WIDTH = int(os.environ.get('POSTER_MIN_WIDTH', '200') or 200)
POSTER_MIN_HEIGHT = int(os.environ.get('POSTER_MIN_HEIGHT', '300') or 300)
POSTER_TIMEOUT = int(os.environ.get('POSTER_TIMEOUT', '15') or 15)

# 请求头
DEFAULT_REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
}

# 中间件配置
DOWNLOADER_MIDDLEWARES = {
    'anime_spider.middlewares.ProxyMiddleware': 100,
    'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': 110,
    'anime_spider.middlewares.RandomUserAgentMiddleware': 400,
    'anime_spider.middlewares.RetryMiddleware': 550,
}

# Pipeline 配置
ITEM_PIPELINES = {
    'anime_spider.pipelines.AnimePipeline': 300,
}

# User-Agent 池
USER_AGENT_LIST = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
]

# Scrapy-Redis 配置（可选，用于分布式）
# SCHEDULER = 'scrapy_redis.scheduler.Scheduler'
# DUPEFILTER_CLASS = 'scrapy_redis.dupefilter.RFPDupeFilter'
# REDIS_URL = 'redis://localhost:6379'
