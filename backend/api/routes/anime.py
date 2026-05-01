"""动画相关 API 接口"""

import math
import re
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query

from api.database import get_db
from api.models import (
    AnimeDetail,
    AnimeFiltersResponse,
    AnimeListItem,
    AnimeListResponse,
    PaginationMeta,
    PlaySourceOut,
)

router = APIRouter(prefix='/api/anime', tags=['动画'])


@router.get('', response_model=AnimeListResponse)
async def list_anime(
    page: int = Query(1, ge=1, description='页码'),
    page_size: int = Query(20, ge=1, le=100, description='每页数量'),
    keyword: str = Query(None, max_length=100, description='搜索关键词（标题/声优）'),
    year: int = Query(None, description='按年份筛选'),
    genre: str = Query(None, description='按类型筛选'),
    director: str = Query(None, description='按导演筛选'),
    incremental_only: bool = Query(False, description='只看最近发现增量的动画'),
    playable_only: bool = Query(False, description='只看存在可播放源的动画'),
    sort_by: str = Query('discovered_at', description='排序字段: discovered_at, year, title'),
    sort_order: str = Query('desc', description='排序方向: asc / desc'),
):
    """获取动画列表，支持分页、搜索、筛选"""
    db = get_db()
    col = db['anime']

    # 构建查询条件（用户输入需转义防注入）
    query = {}
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
    if genre:
        query['genres'] = {'$regex': re.escape(genre.strip()), '$options': 'i'}
    if director:
        query['director'] = {'$regex': re.escape(director.strip()), '$options': 'i'}
    if incremental_only:
        query['incremental_found'] = True
    if playable_only:
        query['play_sources.0'] = {'$exists': True}

    # 排序
    sort_dir = -1 if sort_order == 'desc' else 1
    sort_field = sort_by if sort_by in (
        'discovered_at', 'year', 'title', 'quality_score', 'latest_episode',
        'total_episode_count', 'incremental_priority', 'last_incremental_check'
    ) else 'discovered_at'

    # 查询总数
    total = await col.count_documents(query)
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    # 分页查询
    skip = (page - 1) * page_size
    cursor = col.find(query).sort(sort_field, sort_dir).skip(skip).limit(page_size)

    items = []
    async for doc in cursor:
        item = AnimeListItem(
            _id=str(doc['_id']),
            title=doc.get('title'),
            original_title=doc.get('original_title'),
            aliases=doc.get('aliases', []),
            year=doc.get('year'),
            director=doc.get('director'),
            poster_url=doc.get('poster_url'),
            poster_local=doc.get('poster_local'),
            genres=doc.get('genres', []),
            source_domain=doc.get('source_domain'),
            site_type=doc.get('site_type'),
            quality_score=doc.get('quality_score'),
            latest_episode=doc.get('latest_episode'),
            total_episode_count=doc.get('total_episode_count'),
            incremental_found=doc.get('incremental_found'),
            new_episode_count=doc.get('new_episode_count'),
            last_incremental_check=doc.get('last_incremental_check'),
            incremental_priority=doc.get('incremental_priority'),
            play_source_count=len(doc.get('play_sources', [])),
            discovered_at=doc.get('discovered_at'),
        )
        items.append(item)

    return AnimeListResponse(
        data=items,
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        ),
    )


@router.get('/filters', response_model=AnimeFiltersResponse)
async def get_anime_filters(
    playable_only: bool = Query(True, description='只统计有播放源的动画'),
):
    """获取前端筛选所需的年份和分类候选。"""
    db = get_db()
    col = db['anime']

    match_query = {'play_sources.0': {'$exists': True}} if playable_only else {}

    year_pipeline = [
        {'$match': {**match_query, 'year': {'$ne': None}}},
        {'$group': {'_id': '$year'}},
        {'$sort': {'_id': -1}},
    ]
    genre_pipeline = [
        {'$match': match_query},
        {'$unwind': '$genres'},
        {'$match': {'genres': {'$ne': None, '$ne': ''}}},
        {'$group': {'_id': '$genres', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1, '_id': 1}},
        {'$limit': 40},
    ]

    year_docs = await col.aggregate(year_pipeline).to_list(100)
    genre_docs = await col.aggregate(genre_pipeline).to_list(40)

    return AnimeFiltersResponse(
        years=[doc['_id'] for doc in year_docs if isinstance(doc.get('_id'), int)],
        genres=[doc['_id'] for doc in genre_docs if doc.get('_id')],
    )


@router.get('/{anime_id}', response_model=AnimeDetail)
async def get_anime(anime_id: str):
    """获取动画详情"""
    db = get_db()
    col = db['anime']

    try:
        doc = await col.find_one({'_id': ObjectId(anime_id)})
    except Exception:
        raise HTTPException(status_code=400, detail='无效的 ID 格式')

    if not doc:
        raise HTTPException(status_code=404, detail='动画不存在')

    play_sources = []
    for src in doc.get('play_sources', []):
        episodes = [
            {'episode': ep.get('episode'), 'url': ep.get('url', '')}
            for ep in src.get('episodes', [])
        ]
        play_sources.append(PlaySourceOut(
            domain=src.get('domain', ''),
            source_name=src.get('source_name'),
            provider_id=src.get('provider_id'),
            source_id=src.get('source_id'),
            episodes=episodes,
            quality=src.get('quality'),
            raw_url=src.get('raw_url'),
            episode_count=src.get('episode_count'),
            latest_episode=src.get('latest_episode'),
            new_episode_count=src.get('new_episode_count'),
            added_at=src.get('added_at'),
            last_episode_update=src.get('last_episode_update'),
        ))

    return AnimeDetail(
        _id=str(doc['_id']),
        title=doc.get('title'),
        original_title=doc.get('original_title'),
        aliases=doc.get('aliases', []),
        year=doc.get('year'),
        director=doc.get('director'),
        voice_actors=doc.get('voice_actors', []),
        synopsis=doc.get('synopsis'),
        poster_url=doc.get('poster_url'),
        poster_local=doc.get('poster_local'),
        source_urls=doc.get('source_urls', []),
        source_domain=doc.get('source_domain'),
        extractor_name=doc.get('extractor_name'),
        extractor_confidence=doc.get('extractor_confidence'),
        site_type=doc.get('site_type'),
        quality_score=doc.get('quality_score'),
        latest_episode=doc.get('latest_episode'),
        total_episode_count=doc.get('total_episode_count'),
        new_episode_count=doc.get('new_episode_count'),
        incremental_found=doc.get('incremental_found'),
        last_incremental_check=doc.get('last_incremental_check'),
        incremental_priority=doc.get('incremental_priority'),
        genres=doc.get('genres', []),
        play_sources=play_sources,
        discovered_at=doc.get('discovered_at'),
        updated_at=doc.get('updated_at'),
    )


@router.get('/{anime_id}/sources', response_model=list[PlaySourceOut])
async def get_anime_sources(anime_id: str):
    """获取动画的播放源列表"""
    db = get_db()
    col = db['anime']

    try:
        doc = await col.find_one({'_id': ObjectId(anime_id)}, {'play_sources': 1})
    except Exception:
        raise HTTPException(status_code=400, detail='无效的 ID 格式')

    if not doc:
        raise HTTPException(status_code=404, detail='动画不存在')

    sources = []
    for src in doc.get('play_sources', []):
        episodes = [
            {'episode': ep.get('episode'), 'url': ep.get('url', '')}
            for ep in src.get('episodes', [])
        ]
        sources.append(PlaySourceOut(
            domain=src.get('domain', ''),
            source_name=src.get('source_name'),
            provider_id=src.get('provider_id'),
            source_id=src.get('source_id'),
            episodes=episodes,
            quality=src.get('quality'),
            raw_url=src.get('raw_url'),
            episode_count=src.get('episode_count'),
            latest_episode=src.get('latest_episode'),
            new_episode_count=src.get('new_episode_count'),
            added_at=src.get('added_at'),
            last_episode_update=src.get('last_episode_update'),
        ))

    return sources
