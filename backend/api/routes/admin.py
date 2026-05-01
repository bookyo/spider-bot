"""管理后台 API"""

from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.admin_auth import require_admin_api_key
from api.database import get_db
from api.scheduler import (
    DEFAULT_SETTINGS,
    ensure_admin_settings,
    get_admin_settings,
    run_incremental_job,
    start_source_crawl_job,
    start_source_discovery_job,
)

router = APIRouter(prefix='/api/admin', tags=['管理后台'], dependencies=[Depends(require_admin_api_key)])


class CrawlSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    domain: str | None = None
    seed_url: str | None = None
    homepage_url: str | None = None
    category_pages: list[str] = []
    recent_pages: list[str] = []
    max_depth: int = Field(default=3, ge=0, le=10)
    discovery_max_depth: int = Field(default=1, ge=0, le=2)
    enabled: bool = True
    notes: str | None = None


class CrawlSourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    domain: str | None = None
    seed_url: str | None = None
    homepage_url: str | None = None
    category_pages: list[str] | None = None
    recent_pages: list[str] | None = None
    max_depth: int | None = Field(default=None, ge=0, le=10)
    discovery_max_depth: int | None = Field(default=None, ge=0, le=2)
    enabled: bool | None = None
    notes: str | None = None


class AdminSettingsUpdate(BaseModel):
    auto_incremental_enabled: bool | None = None
    incremental_interval_minutes: int | None = Field(default=None, ge=5, le=1440)
    incremental_limit: int | None = Field(default=None, ge=1, le=500)
    incremental_min_hours: int | None = Field(default=None, ge=1, le=720)
    auto_discover_enabled: bool | None = None
    auto_source_discovery_enabled: bool | None = None
    source_discovery_interval_minutes: int | None = Field(default=None, ge=5, le=1440)


@router.get('/settings')
async def admin_get_settings():
    settings = await get_admin_settings()
    settings['_id'] = str(settings['_id'])
    return settings


@router.put('/settings')
async def admin_update_settings(payload: AdminSettingsUpdate):
    await ensure_admin_settings()
    db = get_db()
    updates = {key: value for key, value in payload.model_dump().items() if value is not None}
    if not updates:
        settings = await get_admin_settings()
        settings['_id'] = str(settings['_id'])
        return settings

    updates['updated_at'] = datetime.utcnow()
    await db['app_settings'].update_one({'_id': 'admin'}, {'$set': updates})
    settings = await get_admin_settings()
    settings['_id'] = str(settings['_id'])
    return settings


@router.get('/sources')
async def admin_list_sources():
    db = get_db()
    cursor = db['crawl_sources'].find({}).sort('created_at', -1)
    data = []
    async for doc in cursor:
        doc['_id'] = str(doc['_id'])
        data.append(doc)
    return {'data': data}


@router.post('/sources')
async def admin_create_source(payload: CrawlSourceCreate):
    if not payload.domain and not payload.seed_url:
        raise HTTPException(status_code=400, detail='domain 和 seed_url 至少提供一个')

    db = get_db()
    now = datetime.utcnow()
    doc = {
        'name': payload.name.strip(),
        'domain': (payload.domain or '').strip().lower() or None,
        'seed_url': (payload.seed_url or '').strip() or None,
        'homepage_url': (payload.homepage_url or '').strip() or None,
        'category_pages': [str(value).strip() for value in (payload.category_pages or []) if str(value).strip()],
        'recent_pages': [str(value).strip() for value in (payload.recent_pages or []) if str(value).strip()],
        'max_depth': payload.max_depth,
        'discovery_max_depth': payload.discovery_max_depth,
        'enabled': payload.enabled,
        'notes': payload.notes,
        'source_type': 'manual',
        'last_run_at': None,
        'last_run_status': None,
        'last_run_output': None,
        'last_discovery_at': None,
        'last_discovery_status': None,
        'created_at': now,
        'updated_at': now,
    }
    result = await db['crawl_sources'].insert_one(doc)
    doc['_id'] = str(result.inserted_id)
    return doc


@router.patch('/sources/{source_id}')
async def admin_update_source(source_id: str, payload: CrawlSourceUpdate):
    db = get_db()
    try:
        oid = ObjectId(source_id)
    except Exception:
        raise HTTPException(status_code=400, detail='无效的 source_id')

    updates = {key: value for key, value in payload.model_dump().items() if value is not None}
    if 'domain' in updates:
        updates['domain'] = updates['domain'].strip().lower() or None
    if 'seed_url' in updates:
        updates['seed_url'] = updates['seed_url'].strip() or None
    if 'homepage_url' in updates:
        updates['homepage_url'] = updates['homepage_url'].strip() or None
    if 'category_pages' in updates and updates['category_pages'] is not None:
        updates['category_pages'] = [str(value).strip() for value in updates['category_pages'] if str(value).strip()]
    if 'recent_pages' in updates and updates['recent_pages'] is not None:
        updates['recent_pages'] = [str(value).strip() for value in updates['recent_pages'] if str(value).strip()]
    if 'name' in updates:
        updates['name'] = updates['name'].strip()
    updates['updated_at'] = datetime.utcnow()

    await db['crawl_sources'].update_one({'_id': oid}, {'$set': updates})
    doc = await db['crawl_sources'].find_one({'_id': oid})
    if not doc:
        raise HTTPException(status_code=404, detail='爬虫源不存在')
    doc['_id'] = str(doc['_id'])
    return doc


@router.post('/sources/{source_id}/crawl')
async def admin_run_source_crawl(source_id: str):
    db = get_db()
    try:
        oid = ObjectId(source_id)
    except Exception:
        raise HTTPException(status_code=400, detail='无效的 source_id')

    doc = await db['crawl_sources'].find_one({'_id': oid})
    if not doc:
        raise HTTPException(status_code=404, detail='爬虫源不存在')

    task = await start_source_crawl_job(doc, force=False)
    return {'ok': task.get('started', False), **task}


@router.post('/tasks/incremental/run')
async def admin_run_incremental():
    result = await run_incremental_job(force=False)
    return result


@router.post('/tasks/source-discovery/run')
async def admin_run_source_discovery():
    result = await start_source_discovery_job(force=False)
    return result


@router.get('/overview')
async def admin_overview():
    db = get_db()
    settings = await get_admin_settings()
    source_count = await db['crawl_sources'].count_documents({})
    enabled_count = await db['crawl_sources'].count_documents({'enabled': True})
    return {
        'settings': {
            key: settings.get(key, DEFAULT_SETTINGS.get(key))
            for key in [
                'auto_incremental_enabled',
                'incremental_interval_minutes',
                'incremental_limit',
                'incremental_min_hours',
                'auto_discover_enabled',
                'auto_source_discovery_enabled',
                'source_discovery_interval_minutes',
                'last_incremental_started_at',
                'last_incremental_finished_at',
                'last_incremental_status',
                'last_incremental_output',
                'last_source_discovery_started_at',
                'last_source_discovery_finished_at',
                'last_source_discovery_status',
                'last_source_discovery_output',
            ]
        },
        'source_count': source_count,
        'enabled_source_count': enabled_count,
    }
