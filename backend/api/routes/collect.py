"""采集源管理 API"""

import re
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.admin_auth import require_admin_api_key
from api.database import get_db
from services.collect_engine import (
    collect_engine,
    build_collect_run_options,
    normalize_collect_range,
    normalize_top_level_json_types,
    extract_types_from_items,
    TIME_RANGE,
)
from services.collect_task_runner import collect_task_runner

router = APIRouter(
    prefix='/api/admin/collect',
    tags=['采集源管理'],
    dependencies=[Depends(require_admin_api_key)],
)

COLLECT_RANGE_OPTIONS = list(TIME_RANGE.keys())


# --- Pydantic 模型 ---

class CollectSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=1, max_length=2000)
    type: str = Field(default='json', pattern='^(json|xml)$')
    mid: int = Field(default=1)
    appid: str = Field(default='')
    appkey: str = Field(default='')
    bind: bool = Field(default=False)
    status: bool = Field(default=True)


class CollectSourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    url: str | None = Field(default=None, min_length=1, max_length=2000)
    type: str | None = Field(default=None, pattern='^(json|xml)$')
    mid: int | None = None
    appid: str | None = None
    appkey: str | None = None
    bind: bool | None = None
    status: bool | None = None


class CollectRunRequest(BaseModel):
    range: str = Field(default='today')


class CollectTypeBindingSave(BaseModel):
    bindings: list[dict] = []


# --- 工具函数 ---

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_url(value: str) -> str:
    value = str(value or '').strip()
    if not value:
        return ''
    parsed = urlparse(value)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query = [(k, v) for k, v in query if v != '']
    query.sort(key=lambda x: (x[0], x[1]))
    return urlunparse((
        parsed.scheme or 'http',
        parsed.netloc,
        parsed.path,
        parsed.params,
        urlencode(query),
        '',
    ))


def _to_id(value) -> str:
    if value is None:
        return ''
    if isinstance(value, dict) and '_id' in value:
        return str(value['_id'])
    return str(value)


def _sort_by_source_type_id(rows: list[dict]) -> list[dict]:
    def key(r: dict):
        sid = str(r.get('source_type_id', ''))
        try:
            return (0, int(sid), '')
        except ValueError:
            return (1, 0, sid)
    return sorted(rows, key=key)


# --- API 路由 ---

@router.get('/sources')
async def list_collect_sources():
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail='数据库未连接')
    docs = await db['collect_sources'].find({'mid': 1}).sort('updated_at', -1).to_list(None)
    for doc in docs:
        doc['_id'] = str(doc['_id'])
    return {'data': docs}


@router.post('/sources')
async def create_collect_source(payload: CollectSourceCreate):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail='数据库未连接')

    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail='采集源名称不能为空')

    url = _normalize_url(payload.url)
    if not url:
        raise HTTPException(status_code=400, detail='接口地址不能为空')

    # 检查重复
    existing = await db['collect_sources'].find_one({
        'url': url,
        'mid': 1,
    })
    if existing:
        raise HTTPException(status_code=400, detail='相同接口地址的采集源已存在')

    now = _now()
    doc = {
        'name': name,
        'url': url,
        'type': payload.type,
        'mid': payload.mid,
        'appid': payload.appid,
        'appkey': payload.appkey,
        'bind': payload.bind,
        'status': payload.status,
        'filter': {
            'area': '',
            'year': '',
            'class': '',
            'type': [],
        },
        'last_collect': None,
        'collect_num': 0,
        'created_at': now,
        'updated_at': now,
    }
    result = await db['collect_sources'].insert_one(doc)
    doc['_id'] = str(result.inserted_id)
    return doc


@router.put('/sources/{source_id}')
async def update_collect_source(source_id: str, payload: CollectSourceUpdate):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail='数据库未连接')

    try:
        oid = ObjectId(source_id)
    except Exception:
        raise HTTPException(status_code=400, detail='无效的 source_id')

    existing = await db['collect_sources'].find_one({'_id': oid})
    if not existing:
        raise HTTPException(status_code=404, detail='采集源不存在')

    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if 'name' in updates:
        updates['name'] = updates['name'].strip()
    if 'url' in updates:
        normalized = _normalize_url(updates['url'])
        if not normalized:
            raise HTTPException(status_code=400, detail='接口地址不能为空')
        # 检查重复
        dup = await db['collect_sources'].find_one({
            'url': normalized,
            'mid': 1,
            '_id': {'$ne': oid},
        })
        if dup:
            raise HTTPException(status_code=400, detail='相同接口地址的采集源已存在')
        updates['url'] = normalized

    updates['updated_at'] = _now()
    await db['collect_sources'].update_one({'_id': oid}, {'$set': updates})

    doc = await db['collect_sources'].find_one({'_id': oid})
    if doc:
        doc['_id'] = str(doc['_id'])
    return doc


@router.delete('/sources/{source_id}')
async def delete_collect_source(source_id: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail='数据库未连接')

    try:
        oid = ObjectId(source_id)
    except Exception:
        raise HTTPException(status_code=400, detail='无效的 source_id')

    await db['collect_sources'].delete_one({'_id': oid})
    await db['collect_type_bindings'].delete_many({'collect_source': oid})
    return {'ok': True}


@router.post('/sources/{source_id}/test')
async def test_collect_source(source_id: str):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail='数据库未连接')

    try:
        oid = ObjectId(source_id)
    except Exception:
        raise HTTPException(status_code=400, detail='无效的 source_id')

    source = await db['collect_sources'].find_one({'_id': oid})
    if not source:
        raise HTTPException(status_code=404, detail='采集源不存在')

    try:
        import httpx
        params = {'ac': 'list', 'pg': 1, 'h': 24}
        if source.get('appid'):
            params['appid'] = source['appid']
        if source.get('appkey'):
            params['appkey'] = source['appkey']

        url = collect_engine.build_request_url(source, params)
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            text = resp.text[:500]
        return {'ok': True, 'message': '连接成功', 'preview': text}
    except Exception as e:
        return {'ok': False, 'message': f'连接失败: {e}'}


@router.post('/sources/{source_id}/run')
async def run_collect_source(source_id: str, payload: CollectRunRequest = CollectRunRequest()):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail='数据库未连接')

    try:
        oid = ObjectId(source_id)
    except Exception:
        raise HTTPException(status_code=400, detail='无效的 source_id')

    source = await db['collect_sources'].find_one({'_id': oid})
    if not source:
        raise HTTPException(status_code=404, detail='采集源不存在')
    if not source.get('status', True):
        raise HTTPException(status_code=400, detail='采集源已禁用')

    options = build_collect_run_options({'range': payload.range, 'type': payload.range})

    try:
        task = await collect_task_runner.enqueue(
            source_id=str(source['_id']),
            range_type=options['type'],
            trigger='manual',
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    msg = (
        task.get('enqueue_message')
        if task.get('reused_existing')
        else '已加入后台采集任务'
    )
    task_id = str(task.get('_id', ''))
    return {'ok': True, 'message': msg, 'task_id': task_id, 'task': task}


@router.get('/tasks')
async def list_collect_tasks(source_id: str | None = None):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail='数据库未连接')

    await collect_task_runner._fail_stale_tasks()

    filter_dict: dict = {}
    if source_id:
        try:
            filter_dict['collect_source'] = ObjectId(source_id)
        except Exception:
            raise HTTPException(status_code=400, detail='无效的 source_id')

    docs = await db['collect_tasks'].find(filter_dict).sort('created_at', -1).limit(30).to_list(None)
    for doc in docs:
        doc['_id'] = str(doc['_id'])
        if doc.get('collect_source'):
            doc['collect_source'] = str(doc['collect_source'])
    return {'data': docs}


@router.get('/tasks/{task_id}')
async def get_collect_task(task_id: str):
    task = await collect_task_runner.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='任务不存在')
    return {'data': task}


@router.get('/ranges')
async def list_collect_ranges():
    """返回可用的采集范围选项"""
    return {
        'options': [
            {'key': k, 'label': v} for k, v in {
                'today': '今日更新（1天内）',
                '2day': '2日内更新',
                'week': '本周更新',
                'month': '30日内更新',
                '3month': '90日内更新',
                'all': '全量采集',
            }.items()
        ],
    }


@router.get('/sources/{source_id}/bindings')
async def get_collect_bindings(source_id: str):
    """获取采集源的类型绑定"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail='数据库未连接')

    try:
        oid = ObjectId(source_id)
    except Exception:
        raise HTTPException(status_code=400, detail='无效的 source_id')

    source = await db['collect_sources'].find_one({'_id': oid})
    if not source:
        raise HTTPException(status_code=404, detail='采集源不存在')

    bindings = await db['collect_type_bindings'].find({'collect_source': oid}).to_list(None)

    # 拉取远程类型列表
    remote_types: list[dict] = []
    remote_type_error = ''
    try:
        remote_types = await collect_engine.fetch_types(source)
    except Exception as e:
        remote_type_error = str(e)

    # 拉取本地类型（genres 去重集合）
    local_types = await db['anime'].aggregate([
        {'$unwind': '$genres'},
        {'$group': {'_id': '$genres', 'count': {'$sum': 1}}},
        {'$sort': {'_id': 1}},
    ]).to_list(None)
    local_type_list = [{'name': lt['_id'], 'count': lt.get('count', 0)} for lt in local_types if lt['_id']]

    # 构建绑定行
    binding_map: dict[str, dict] = {}
    for b in bindings:
        b['_id'] = str(b['_id'])
        binding_map[str(b.get('source_type_id', ''))] = b

    rows = []
    seen = set()

    for rt in remote_types:
        sid = str(rt.get('type_id', '')).strip()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        b = binding_map.get(sid)
        rows.append({
            'source_type_id': sid,
            'source_type_name': str(rt.get('type_name', '')).strip(),
            'local_type': b.get('local_type', '') if b else '',
        })

    for b in bindings:
        sid = str(b.get('source_type_id', '')).strip()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        rows.append({
            'source_type_id': sid,
            'source_type_name': str(b.get('source_type_name', '')).strip(),
            'local_type': b.get('local_type', ''),
        })

    rows = _sort_by_source_type_id(rows)

    return {
        'source': {**source, '_id': str(source['_id'])} if source else None,
        'bindings': rows,
        'local_types': local_type_list,
        'remote_type_error': remote_type_error,
    }


@router.post('/sources/{source_id}/bindings')
async def save_collect_bindings(source_id: str, payload: CollectTypeBindingSave):
    """保存采集源的类型绑定"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail='数据库未连接')

    try:
        oid = ObjectId(source_id)
    except Exception:
        raise HTTPException(status_code=400, detail='无效的 source_id')

    source = await db['collect_sources'].find_one({'_id': oid})
    if not source:
        raise HTTPException(status_code=404, detail='采集源不存在')

    await db['collect_type_bindings'].delete_many({'collect_source': oid})

    if payload.bindings:
        docs = []
        for b in payload.bindings:
            sid = str(b.get('sourceTypeId', b.get('source_type_id', ''))).strip()
            lt = b.get('localType', b.get('local_type', ''))
            lt = str(lt).strip() if lt is not None else ''
            if not sid or not lt:
                continue
            docs.append({
                'collect_source': oid,
                'source_type_id': sid,
                'source_type_name': str(b.get('sourceTypeName', b.get('source_type_name', ''))).strip(),
                'local_type': lt,
            })
        if docs:
            await db['collect_type_bindings'].insert_many(docs)

    return {'ok': True}


# --- 采集定时任务管理 ---

class TimingTaskUpdate(BaseModel):
    status: int | None = None
    weeks: str | None = None
    hours: str | None = None
    monthdays: str | None = None


@router.get('/timing')
async def list_collect_timing_tasks():
    """返回所有采集定时任务配置"""
    from config.collect_timing import COLLECT_TIMING_TASKS

    return {'data': [
        {
            'id': idx,
            **task,
        }
        for idx, task in enumerate(COLLECT_TIMING_TASKS)
    ]}


@router.put('/timing/{task_id}')
async def update_collect_timing_task(task_id: int, payload: TimingTaskUpdate):
    """更新采集定时任务设置"""
    from config.collect_timing import COLLECT_TIMING_TASKS

    if task_id < 0 or task_id >= len(COLLECT_TIMING_TASKS):
        raise HTTPException(status_code=404, detail='定时任务不存在')

    task = COLLECT_TIMING_TASKS[task_id]
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    task.update(updates)

    return {'ok': True, 'data': {'id': task_id, **task}}


@router.post('/timing/{task_id}/run')
async def run_collect_timing_task(task_id: int):
    """手动执行采集定时任务"""
    from config.collect_timing import COLLECT_TIMING_TASKS

    if task_id < 0 or task_id >= len(COLLECT_TIMING_TASKS):
        raise HTTPException(status_code=404, detail='定时任务不存在')

    task = COLLECT_TIMING_TASKS[task_id]
    if task.get('file') != 'collect':
        raise HTTPException(status_code=400, detail='仅支持采集类定时任务')

    range_type = task.get('param', {}).get('type', '1day')
    tasks = await collect_task_runner.enqueue_for_all_sources(
        range_type=range_type,
        trigger='scheduler',
    )

    return {
        'ok': True,
        'message': f'已加入后台采集任务，共 {len(tasks)} 个采集源',
        'data': {
            'queued': len(tasks),
            'range': range_type,
        },
    }
