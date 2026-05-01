"""搜索关键词配置 - 用于内容检测和域名发现"""

# 动画内容检测关键词
ANIME_CONTENT_KEYWORDS = [
    # 中文关键词
    '动漫', '动画', '番剧', '新番', '连载',
    '完结', '剧场版', 'OVA', 'OAD', '声优',
    '配音', '字幕组', '生肉', '熟肉', 'BD',
    '蓝光', 'WEB-DL', '720p', '1080p',
    # 日文关键词
    'アニメ', '新番組', '声優', '放送',
    # 英文关键词
    'anime', 'subbed', 'dubbed', 'episode',
    'season', 'ova', 'special',
]

# URL 路径模式 - 识别动画详情/播放页
ANIME_URL_PATTERNS = [
    r'/play/',
    r'/detail/',
    r'/anime/',
    r'/video/',
    r'/vod/',
    r'/movie/',
    r'/tv/',
    r'/show/',
    r'/episode/',
    r'/ep/',
    r'/bangumi/',
    r'/donghua/',
    r'/dongman/',
]

# 动画站点特征关键词（用于域名验证）
ANIME_SITE_KEYWORDS = [
    '动漫', '动画', '番剧', '新番',
    '在线观看', '免费观看', '高清',
    '播放列表', '动漫排行', '动漫推荐',
    'anime', 'dongman', 'acg',
]
