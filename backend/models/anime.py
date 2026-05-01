"""动画数据模型 - MongoDB 文档结构定义"""

# MongoDB anime collection 文档结构:
#
# {
#     "_id": ObjectId,
#     "title": str,              # 标题
#     "original_title": str,     # 原始标题（日文/英文）
#     "year": int,               # 年份
#     "director": str,           # 导演
#     "voice_actors": [str],     # 声优列表
#     "synopsis": str,           # 简介
#     "poster_url": str,         # 海报图URL
#     "source_urls": [str],      # 来源页面URL列表
#     "source_domain": str,      # 来源域名
#     "genres": [str],           # 类型标签
#     "dedup_key": str,          # 去重键 (MD5: title + year + director)
#     "play_sources": [          # 播放源列表
#         {
#             "domain": str,         # 播放源域名
#             "source_name": str,    # 播放线路名
#             "episodes": [          # 分集列表
#                 {
#                     "episode": str,    # 集数 (如 "01")
#                     "url": str         # m3u8 链接
#                 }
#             ],
#             "quality": str,        # 画质
#             "raw_url": str,        # 原始播放页URL
#             "episode_count": int,  # 当前源总集数
#             "latest_episode": str, # 当前源最新集
#             "last_episode_update": datetime,  # 最近新增分集时间
#             "added_at": datetime   # 添加时间
#         }
#     ],
#     "latest_episode": str,    # 动画维度最新集
#     "total_episode_count": int,  # 动画维度总集数
#     "new_episode_count": int,    # 本次新增集数
#     "incremental_found": bool,   # 本次是否发现新集
#     "discovered_at": datetime, # 发现时间
#     "updated_at": datetime     # 更新时间
# }

ANIME_SCHEMA = {
    "title": {"type": "string", "required": True},
    "original_title": {"type": "string"},
    "year": {"type": "integer"},
    "director": {"type": "string"},
    "voice_actors": {"type": "array", "items": "string"},
    "synopsis": {"type": "string"},
    "poster_url": {"type": "string"},
    "source_urls": {"type": "array", "items": "string"},
    "source_domain": {"type": "string"},
    "genres": {"type": "array", "items": "string"},
    "dedup_key": {"type": "string", "required": True, "unique": True},
    "play_sources": {
        "type": "array",
        "items": {
            "domain": {"type": "string"},
            "episodes": {
                "type": "array",
                "items": {
                    "episode": {"type": "string"},
                    "url": {"type": "string"},
                }
            },
            "quality": {"type": "string"},
            "raw_url": {"type": "string"},
            "episode_count": {"type": "integer"},
            "latest_episode": {"type": "string"},
            "last_episode_update": {"type": "datetime"},
            "added_at": {"type": "datetime"},
        }
    },
    "latest_episode": {"type": "string"},
    "total_episode_count": {"type": "integer"},
    "new_episode_count": {"type": "integer"},
    "incremental_found": {"type": "boolean"},
    "discovered_at": {"type": "datetime"},
    "updated_at": {"type": "datetime"},
}
