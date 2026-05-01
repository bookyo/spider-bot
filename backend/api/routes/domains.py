"""域名相关 API 接口"""

import math
import re
from fastapi import APIRouter, HTTPException, Query

from api.database import get_db
from api.models import DomainItem, DomainListResponse, PaginationMeta

router = APIRouter(prefix='/api/domains', tags=['域名'])


@router.get('', response_model=DomainListResponse)
async def list_domains(
    page: int = Query(1, ge=1, description='页码'),
    page_size: int = Query(20, ge=1, le=100, description='每页数量'),
    status: str = Query(None, pattern='^(pending|crawling|completed|failed)$', description='状态筛选'),
    is_anime_site: bool = Query(None, description='是否为动漫站点'),
    sort_by: str = Query('discovered_at', description='排序字段: discovered_at, priority_score, health_score'),
    sort_order: str = Query('desc', description='排序方向: asc / desc'),
):
    """获取域名列表"""
    db = get_db()
    col = db['discovered_domains']

    query = {}
    if status:
        query['status'] = status
    if is_anime_site is not None:
        query['is_anime_site'] = is_anime_site

    total = await col.count_documents(query)
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    skip = (page - 1) * page_size
    sort_dir = -1 if sort_order == 'desc' else 1
    sort_field = sort_by if sort_by in ('discovered_at', 'priority_score', 'health_score') else 'discovered_at'
    cursor = col.find(query).sort(sort_field, sort_dir).skip(skip).limit(page_size)

    items = []
    async for doc in cursor:
        items.append(DomainItem(
            _id=str(doc['_id']),
            domain=doc.get('domain', ''),
            source=doc.get('source'),
            is_anime_site=doc.get('is_anime_site', False),
            status=doc.get('status'),
            site_type=doc.get('site_type'),
            last_error=doc.get('last_error'),
            retry_count=doc.get('retry_count'),
            priority_score=doc.get('priority_score'),
            total_crawls=doc.get('total_crawls'),
            success_crawls=doc.get('success_crawls'),
            success_rate=doc.get('success_rate'),
            total_anime_found=doc.get('total_anime_found'),
            avg_quality_score=doc.get('avg_quality_score'),
            health_score=doc.get('health_score'),
            last_crawled=doc.get('last_crawled'),
            discovered_at=doc.get('discovered_at'),
        ))

    return DomainListResponse(
        data=items,
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        ),
    )


@router.get('/{domain:path}', response_model=DomainItem)
async def get_domain(domain: str):
    """获取域名详情"""
    # 验证域名格式
    if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$', domain) or len(domain) > 253:
        raise HTTPException(status_code=400, detail='无效的域名格式')

    db = get_db()
    col = db['discovered_domains']

    doc = await col.find_one({'domain': domain.lower()})
    if not doc:
        raise HTTPException(status_code=404, detail='域名不存在')

    return DomainItem(
        _id=str(doc['_id']),
        domain=doc.get('domain', ''),
        source=doc.get('source'),
        is_anime_site=doc.get('is_anime_site', False),
        status=doc.get('status'),
        site_type=doc.get('site_type'),
        last_error=doc.get('last_error'),
        retry_count=doc.get('retry_count'),
        priority_score=doc.get('priority_score'),
        total_crawls=doc.get('total_crawls'),
        success_crawls=doc.get('success_crawls'),
        success_rate=doc.get('success_rate'),
        total_anime_found=doc.get('total_anime_found'),
        avg_quality_score=doc.get('avg_quality_score'),
        health_score=doc.get('health_score'),
        last_crawled=doc.get('last_crawled'),
        discovered_at=doc.get('discovered_at'),
    )
