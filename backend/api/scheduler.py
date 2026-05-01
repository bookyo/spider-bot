"""简单的后台定时调度器"""

import asyncio
import logging
import os
from datetime import datetime

from api.database import get_db
from api.task_runner import run_backend_command, spawn_backend_command

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS = {
    'auto_incremental_enabled': False,
    'incremental_interval_minutes': 60,
    'incremental_limit': 20,
    'incremental_min_hours': 6,
    'auto_discover_enabled': False,
    'auto_source_discovery_enabled': False,
    'source_discovery_interval_minutes': 180,
}

_scheduler_task: asyncio.Task | None = None
_source_discovery_task: asyncio.Task | None = None
_incremental_lock = asyncio.Lock()
_source_discovery_lock = asyncio.Lock()


async def ensure_admin_settings():
    db = get_db()
    if db is None:
        return

    col = db['app_settings']
    doc = await col.find_one({'_id': 'admin'})
    if not doc:
        payload = {
            '_id': 'admin',
            **DEFAULT_SETTINGS,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'last_incremental_started_at': None,
            'last_incremental_finished_at': None,
            'last_incremental_status': None,
            'last_incremental_output': None,
            'last_source_discovery_started_at': None,
            'last_source_discovery_finished_at': None,
            'last_source_discovery_status': None,
            'last_source_discovery_output': None,
        }
        await col.insert_one(payload)
        return

    updates = {}
    for key, value in DEFAULT_SETTINGS.items():
        if key not in doc:
            updates[key] = value
    if updates:
        updates['updated_at'] = datetime.utcnow()
        await col.update_one({'_id': 'admin'}, {'$set': updates})


async def get_admin_settings() -> dict:
    await ensure_admin_settings()
    db = get_db()
    return await db['app_settings'].find_one({'_id': 'admin'}) or {'_id': 'admin', **DEFAULT_SETTINGS}


async def run_incremental_job(force: bool = False) -> dict:
    if _incremental_lock.locked() and not force:
        return {'started': False, 'reason': 'incremental job already running'}

    async with _incremental_lock:
        settings = await get_admin_settings()
        db = get_db()
        started_at = datetime.utcnow()
        await db['app_settings'].update_one(
            {'_id': 'admin'},
            {'$set': {
                'last_incremental_started_at': started_at,
                'last_incremental_status': 'running',
                'updated_at': started_at,
            }}
        )

        limit = int(settings.get('incremental_limit') or DEFAULT_SETTINGS['incremental_limit'])
        min_hours = int(settings.get('incremental_min_hours') or DEFAULT_SETTINGS['incremental_min_hours'])
        code, output = await run_backend_command([
            'incremental',
            '--limit', str(limit),
            '--min-hours', str(min_hours),
        ])
        finished_at = datetime.utcnow()
        status = 'success' if code == 0 else 'failed'

        await db['app_settings'].update_one(
            {'_id': 'admin'},
            {'$set': {
                'last_incremental_finished_at': finished_at,
                'last_incremental_status': status,
                'last_incremental_output': output[-4000:],
                'updated_at': finished_at,
            }}
        )
        return {'started': True, 'status': status, 'code': code, 'output': output[-4000:]}


def build_source_discovery_targets(source: dict) -> list[str]:
    seen = set()
    urls: list[str] = []

    def push(value):
        candidate = str(value or '').strip()
        if not candidate or candidate in seen:
            return
        seen.add(candidate)
        urls.append(candidate)

    push(source.get('seed_url'))
    push(source.get('homepage_url'))
    for value in source.get('category_pages') or []:
        push(value)
    for value in source.get('recent_pages') or []:
        push(value)

    domain = str(source.get('domain') or '').strip()
    if not urls and domain:
        push(f'https://{domain}')
        push(f'http://{domain}')

    return urls


async def trigger_source_crawl(source: dict) -> dict:
    args = ['crawl', '--max-depth', str(int(source.get('max_depth') or 3))]
    seed_url = str(source.get('seed_url') or '').strip()
    domain = str(source.get('domain') or '').strip()

    if seed_url:
        args.extend(['-u', seed_url])
    elif domain:
        args.extend(['-d', domain])
    else:
        raise ValueError('source missing domain/seed_url')

    task = await spawn_backend_command(args)
    return task


async def run_source_discovery_job(force: bool = False) -> dict:
    if _source_discovery_lock.locked() and not force:
        return {'started': False, 'reason': 'source discovery job already running'}

    async with _source_discovery_lock:
        db = get_db()
        settings = await get_admin_settings()
        started_at = datetime.utcnow()
        await db['app_settings'].update_one(
            {'_id': 'admin'},
            {'$set': {
                'last_source_discovery_started_at': started_at,
                'last_source_discovery_status': 'running',
                'updated_at': started_at,
            }}
        )

        enabled_sources = []
        cursor = db['crawl_sources'].find({'enabled': True})
        async for doc in cursor:
            enabled_sources.append(doc)

        max_depth_default = 1
        outputs: list[str] = []
        failures = 0
        started = 0

        for source in enabled_sources:
            targets = build_source_discovery_targets(source)
            if not targets:
                continue

            source_max_depth = min(int(source.get('discovery_max_depth') or max_depth_default), 2)
            for target in targets:
                args = ['crawl', '-u', target, '--max-depth', str(source_max_depth)]
                code, output = await run_backend_command(args)
                started += 1
                if code != 0:
                    failures += 1
                compact = f"[{source.get('name')}] {target} -> code={code}"
                if output.strip():
                    compact += f"\n{output[-800:]}"
                outputs.append(compact)

            await db['crawl_sources'].update_one(
                {'_id': source['_id']},
                {'$set': {
                    'last_discovery_at': datetime.utcnow(),
                    'last_discovery_status': 'success' if failures == 0 else 'partial',
                    'updated_at': datetime.utcnow(),
                }}
            )

        finished_at = datetime.utcnow()
        status = 'success' if failures == 0 else ('partial' if started else 'idle')
        await db['app_settings'].update_one(
            {'_id': 'admin'},
            {'$set': {
                'last_source_discovery_finished_at': finished_at,
                'last_source_discovery_status': status,
                'last_source_discovery_output': '\n\n'.join(outputs)[-4000:] if outputs else None,
                'updated_at': finished_at,
            }}
        )
        return {
            'started': True,
            'status': status,
            'source_count': len(enabled_sources),
            'target_count': started,
            'output': ('\n\n'.join(outputs)[-4000:] if outputs else ''),
        }


def is_source_discovery_running() -> bool:
    return _source_discovery_lock.locked() or (_source_discovery_task is not None and not _source_discovery_task.done())


async def start_source_discovery_job(force: bool = False) -> dict:
    global _source_discovery_task

    if is_source_discovery_running() and not force:
        return {'started': False, 'reason': 'source discovery job already running'}

    async def runner():
        try:
            await run_source_discovery_job(force=True)
        except asyncio.CancelledError:
            db = get_db()
            if db is not None:
                now = datetime.utcnow()
                await db['app_settings'].update_one(
                    {'_id': 'admin'},
                    {'$set': {
                        'last_source_discovery_finished_at': now,
                        'last_source_discovery_status': 'cancelled',
                        'last_source_discovery_output': 'source discovery task cancelled',
                        'updated_at': now,
                    }}
                )
            raise
        except Exception as exc:
            logger.exception('[Scheduler] source discovery task failed: %s', exc)
            db = get_db()
            if db is not None:
                now = datetime.utcnow()
                await db['app_settings'].update_one(
                    {'_id': 'admin'},
                    {'$set': {
                        'last_source_discovery_finished_at': now,
                        'last_source_discovery_status': 'failed',
                        'last_source_discovery_output': str(exc)[-4000:],
                        'updated_at': now,
                    }}
                )

    _source_discovery_task = asyncio.create_task(runner(), name='source-discovery-job')
    return {'started': True, 'status': 'running', 'mode': 'background'}


async def scheduler_loop():
    while True:
        try:
            settings = await get_admin_settings()
            if settings.get('auto_incremental_enabled'):
                interval = max(int(settings.get('incremental_interval_minutes') or 60), 5)
                last_started = settings.get('last_incremental_started_at')
                now = datetime.utcnow()
                due = True
                if last_started:
                    due = (now - last_started).total_seconds() >= interval * 60
                if due and not _incremental_lock.locked():
                    logger.info('[Scheduler] running incremental job')
                    await run_incremental_job()
            if settings.get('auto_source_discovery_enabled'):
                interval = max(int(settings.get('source_discovery_interval_minutes') or 180), 5)
                last_started = settings.get('last_source_discovery_started_at')
                now = datetime.utcnow()
                due = True
                if last_started:
                    due = (now - last_started).total_seconds() >= interval * 60
                if due and not is_source_discovery_running():
                    logger.info('[Scheduler] running source discovery job')
                    await start_source_discovery_job()
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception('[Scheduler] loop failed: %s', exc)
            await asyncio.sleep(30)


async def start_scheduler():
    global _scheduler_task
    if os.environ.get('ENABLE_INTERNAL_SCHEDULER', 'true').lower() not in {'1', 'true', 'yes', 'on'}:
        logger.info('[Scheduler] disabled by environment')
        return
    await ensure_admin_settings()
    if _scheduler_task and not _scheduler_task.done():
        return
    _scheduler_task = asyncio.create_task(scheduler_loop(), name='admin-scheduler-loop')
    logger.info('[Scheduler] started')


async def stop_scheduler():
    global _scheduler_task, _source_discovery_task
    if _scheduler_task:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
        _scheduler_task = None
    if _source_discovery_task and not _source_discovery_task.done():
        _source_discovery_task.cancel()
        try:
            await _source_discovery_task
        except asyncio.CancelledError:
            pass
    _source_discovery_task = None
