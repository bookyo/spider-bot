"""播放源数据模型 - MongoDB 文档结构定义"""

# 播放源嵌入在 anime 文档的 play_sources 数组中
#
# 结构示例:
# {
#     "domain": "player.example.com",  # 播放源域名
#     "source_name": "线路1",          # 播放线路名
#     "episodes": [                    # 分集列表
#         {
#             "episode": "01",             # 集数
#             "url": "https://xxx.m3u8"    # m3u8 播放链接
#         },
#         {
#             "episode": "02",
#             "url": "https://xxx.m3u8"
#         }
#     ],
#     "quality": "1080p",              # 画质
#     "raw_url": "https://...",        # 原始播放页URL
#     "episode_count": 12,             # 当前总集数
#     "latest_episode": "12",          # 最新集
#     "last_episode_update": ISODate,  # 最近一次新增分集时间
#     "added_at": ISODate              # 添加时间
# }

PLAY_SOURCE_SCHEMA = {
    "domain": {"type": "string", "required": True},
    "source_name": {"type": "string"},
    "episodes": {
        "type": "array",
        "required": True,
        "items": {
            "episode": {"type": "string"},
            "url": {"type": "string", "required": True},
        }
    },
    "quality": {"type": "string"},
    "raw_url": {"type": "string"},
    "episode_count": {"type": "integer"},
    "latest_episode": {"type": "string"},
    "last_episode_update": {"type": "datetime"},
    "added_at": {"type": "datetime"},
}
