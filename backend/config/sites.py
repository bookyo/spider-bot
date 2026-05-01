"""已知站点规则配置 - 预设的动漫站点列表和解析规则。

规则字段示例:
- detail_selector: 详情页判定选择器
- detail_links: 列表页详情链接选择器
- title/director/voice_actors/synopsis/poster/genres: 字段提取选择器
"""

# 预设的动漫站点域名（可选，作为种子站点）
SEED_DOMAINS = [
    # 用户可以添加已知的动漫站点作为种子
    # 'example-anime.com',
]

# 站点解析规则（可选，针对特定站点的 CSS/XPath 选择器）
# 如果不配置，将使用通用的检测逻辑
SITE_RULES = {
    # 'example.com': {
    #     'detail_selector': '.video-info',
    #     'detail_links': '.module-item a::attr(href)',
    #     'title': 'h1.title::text',
    #     'director': '.info .director::text',
    #     'voice_actors': '.info .actors a::text',
    #     'synopsis': '.description::text',
    #     'poster': '.poster img::attr(src)',
    #     'genres': '.tag a::text',
    # },
}

# 需要排除的域名（广告、搜索引擎等）
EXCLUDED_DOMAINS = [
    'google.com', 'bing.com', 'baidu.com',
    'youtube.com', 'twitter.com', 'facebook.com',
    'instagram.com', 'weibo.com', 'bilibili.com',
    'qq.com', 'taobao.com', 'jd.com',
    'googleapis.com', 'gstatic.com',
    'cloudflare.com', 'amazonaws.com',
]
