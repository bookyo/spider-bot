"""动画列表查询与索引声明。"""

from __future__ import annotations

import re
from typing import Any

ANIME_LIST_COMPOUND_INDEX = [('genres', 1), ('year', 1), ('discovered_at', -1)]
ANIME_LIST_INDEXES = [ANIME_LIST_COMPOUND_INDEX]


def build_anime_list_query(
    *,
    keyword: str | None = None,
    year: int | None = None,
    genre: str | None = None,
    director: str | None = None,
    incremental_only: bool = False,
    playable_only: bool = False,
) -> dict[str, Any]:
    """构建动画列表查询条件。"""
    query: dict[str, Any] = {}

    if keyword:
        escaped = re.escape(keyword.strip())
        query['$or'] = [
            {'title': {'$regex': escaped, '$options': 'i'}},
            {'original_title': {'$regex': escaped, '$options': 'i'}},
            {'aliases': {'$regex': escaped, '$options': 'i'}},
            {'normalized_title': {'$regex': escaped.lower(), '$options': 'i'}},
            {'voice_actors': {'$regex': escaped, '$options': 'i'}},
            {'director': {'$regex': escaped, '$options': 'i'}},
        ]

    if year:
        query['year'] = year

    normalized_genre = str(genre or '').strip()
    if normalized_genre:
        # MongoDB 对数组字段的直接字符串匹配会匹配数组成员，便于命中 multikey 索引。
        query['genres'] = normalized_genre

    if director:
        query['director'] = {'$regex': re.escape(director.strip()), '$options': 'i'}

    if incremental_only:
        query['incremental_found'] = True

    if playable_only:
        query['play_sources.0'] = {'$exists': True}

    return query
