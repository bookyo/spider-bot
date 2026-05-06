"""Scrapy Item 定义 - 动画数据和播放源"""

import scrapy


class AnimeItem(scrapy.Item):
    """动画数据项"""
    title = scrapy.Field()           # 标题
    original_title = scrapy.Field()  # 原始标题（日文/英文）
    year = scrapy.Field()            # 年份
    director = scrapy.Field()        # 导演
    voice_actors = scrapy.Field()    # 声优列表
    synopsis = scrapy.Field()        # 简介
    poster_url = scrapy.Field()      # 海报图URL
    douban_rating = scrapy.Field()   # 豆瓣评分
    imdb_rating = scrapy.Field()     # IMDb 评分
    source_url = scrapy.Field()      # 来源页面URL
    source_domain = scrapy.Field()   # 来源域名
    genres = scrapy.Field()          # 类型标签
    play_sources = scrapy.Field()    # 播放源列表
    discovered_at = scrapy.Field()   # 发现时间
    dedup_key = scrapy.Field()       # 去重键
    extractor_name = scrapy.Field()  # 提取器名称
    extractor_confidence = scrapy.Field()  # 提取置信度
    site_type = scrapy.Field()       # 站型/适配器名
    aliases = scrapy.Field()         # 标题别名
    normalized_title = scrapy.Field()  # 归一化标题
    quality_score = scrapy.Field()   # 质量分
    latest_episode = scrapy.Field()  # 最新集数
    total_episode_count = scrapy.Field()  # 总集数
    incremental_found = scrapy.Field()  # 本次是否发现新集
    new_episode_count = scrapy.Field()  # 本次新增集数
    last_incremental_check = scrapy.Field()  # 最近一次增量巡检时间
    incremental_priority = scrapy.Field()  # 增量巡检优先级


class PlaySourceItem(scrapy.Item):
    """播放源数据项"""
    domain = scrapy.Field()          # 播放源域名
    source_name = scrapy.Field()     # 播放线路名
    provider_id = scrapy.Field()     # 底层播放源提供商弱标识
    source_id = scrapy.Field()       # 当前动画下线路唯一标识
    episodes = scrapy.Field()        # 分集信息列表
    quality = scrapy.Field()         # 画质
    raw_url = scrapy.Field()         # 原始播放页URL
    episode_count = scrapy.Field()   # 当前播放源总集数
    latest_episode = scrapy.Field()  # 当前播放源最新集数
    last_episode_update = scrapy.Field()  # 最近一次新增分集时间


class DomainItem(scrapy.Item):
    """发现的域名数据项"""
    domain = scrapy.Field()          # 域名
    source = scrapy.Field()          # 发现来源（crt_sh/whois/dns_enum）
    discovered_at = scrapy.Field()   # 发现时间
    is_anime_site = scrapy.Field()   # 是否确认为动漫站点
    last_crawled = scrapy.Field()    # 最后爬取时间
    status = scrapy.Field()          # 状态：pending/crawling/completed/failed
    site_type = scrapy.Field()       # 站型/适配器名
    last_error = scrapy.Field()      # 最近一次错误
    retry_count = scrapy.Field()     # 重试次数
    priority_score = scrapy.Field()  # 调度优先级
    total_crawls = scrapy.Field()    # 总抓取次数
    success_crawls = scrapy.Field()  # 成功抓取次数
    success_rate = scrapy.Field()    # 成功率
    total_anime_found = scrapy.Field()  # 累计发现动画数
    avg_quality_score = scrapy.Field()  # 平均质量分
    health_score = scrapy.Field()    # 站点健康度
