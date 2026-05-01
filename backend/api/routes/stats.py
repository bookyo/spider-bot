"""统计 API 接口"""

from fastapi import APIRouter

from api.database import get_db
from api.models import StatsResponse

router = APIRouter(prefix='/api', tags=['统计'])


@router.get('/stats', response_model=StatsResponse)
async def get_stats():
    """获取总体统计数据"""
    db = get_db()
    anime_col = db['anime']
    domain_col = db['discovered_domains']

    total_anime = await anime_col.count_documents({})
    total_domains = await domain_col.count_documents({})
    anime_sites = await domain_col.count_documents({'is_anime_site': True})
    pending_domains = await domain_col.count_documents({'status': 'pending'})
    healthy_domains = await domain_col.count_documents({'health_score': {'$gte': 0.6}})
    failed_domains = await domain_col.count_documents({'status': 'failed'})

    # 播放源总数（聚合）
    pipeline = [
        {'$project': {'count': {'$size': {'$ifNull': ['$play_sources', []]}}}},
        {'$group': {'_id': None, 'total': {'$sum': '$count'}}},
    ]
    result = await anime_col.aggregate(pipeline).to_list(1)
    total_play_sources = result[0]['total'] if result else 0

    # 年份分布（前 20）
    year_pipeline = [
        {'$match': {'year': {'$ne': None}}},
        {'$group': {'_id': '$year', 'count': {'$sum': 1}}},
        {'$sort': {'_id': -1}},
        {'$limit': 20},
    ]
    year_docs = await anime_col.aggregate(year_pipeline).to_list(20)
    year_distribution = {str(doc['_id']): doc['count'] for doc in year_docs}

    # 热门类型（前 10）
    genre_pipeline = [
        {'$unwind': '$genres'},
        {'$group': {'_id': '$genres', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}},
        {'$limit': 10},
    ]
    genre_docs = await anime_col.aggregate(genre_pipeline).to_list(10)
    top_genres = [{'genre': doc['_id'], 'count': doc['count']} for doc in genre_docs]

    quality_pipeline = [
        {'$match': {'quality_score': {'$ne': None}}},
        {'$bucket': {
            'groupBy': '$quality_score',
            'boundaries': [0, 0.4, 0.7, 0.9, 1.1],
            'default': 'other',
            'output': {'count': {'$sum': 1}},
        }},
    ]
    quality_docs = await anime_col.aggregate(quality_pipeline).to_list(10)
    label_map = {
        0: 'low',
        0.4: 'medium',
        0.7: 'good',
        0.9: 'excellent',
    }
    quality_distribution = {}
    for doc in quality_docs:
        key = label_map.get(doc['_id'], str(doc['_id']))
        quality_distribution[key] = doc['count']

    avg_pipeline = [
        {'$match': {'quality_score': {'$ne': None}}},
        {'$group': {'_id': None, 'avg': {'$avg': '$quality_score'}}},
    ]
    avg_docs = await anime_col.aggregate(avg_pipeline).to_list(1)
    avg_anime_quality = round(avg_docs[0]['avg'], 4) if avg_docs else 0.0

    return StatsResponse(
        total_anime=total_anime,
        total_domains=total_domains,
        anime_sites=anime_sites,
        pending_domains=pending_domains,
        total_play_sources=total_play_sources,
        year_distribution=year_distribution,
        top_genres=top_genres,
        healthy_domains=healthy_domains,
        failed_domains=failed_domains,
        avg_anime_quality=avg_anime_quality,
        quality_distribution=quality_distribution,
    )
