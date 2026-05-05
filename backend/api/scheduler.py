"""简单的后台定时调度器"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus
from urllib.parse import urlparse

from bson import ObjectId
from api.database import get_db
from api.task_runner import run_backend_command, run_backend_command_stream, spawn_backend_command
from anime_spider.utils.douban_enrichment import fetch_douban_subject_metadata, search_douban_subject_url
from anime_spider.utils.poster import download_poster

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS = {
    'auto_incremental_enabled': False,
    'incremental_interval_minutes': 60,
    'incremental_limit': 20,
    'incremental_min_hours': 6,
    'auto_discover_enabled': False,
    'auto_source_discovery_enabled': False,
    'source_discovery_interval_minutes': 180,
    'crawler_proxy_url': None,
    'douban_backfill_enabled': False,
    'douban_backfill_interval_minutes': 60,
    'douban_backfill_limit': 50,
    'douban_search_url': 'https://s.stdlang.com/search',
    'douban_backfill_timeout_seconds': 20,
}

_scheduler_task: asyncio.Task | None = None
_source_discovery_task: asyncio.Task | None = None
_douban_backfill_task: asyncio.Task | None = None
_source_crawl_tasks: dict[str, asyncio.Task] = {}
_incremental_lock = asyncio.Lock()
_source_discovery_lock = asyncio.Lock()
_douban_backfill_lock = asyncio.Lock()


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
            'last_douban_backfill_started_at': None,
            'last_douban_backfill_finished_at': None,
            'last_douban_backfill_status': None,
            'last_douban_backfill_output': None,
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


async def _update_backfill_status(payload: dict[str, Any]) -> None:
    db = get_db()
    if db is None:
        return
    payload['updated_at'] = datetime.utcnow()
    await db['app_settings'].update_one({'_id': 'admin'}, {'$set': payload})


def build_crawler_env(settings: dict | None = None) -> dict[str, str]:
    settings = settings or {}
    env = {}
    proxy_url = str(settings.get('crawler_proxy_url') or os.environ.get('CRAWLER_PROXY_URL') or '').strip()
    if proxy_url:
        env['CRAWLER_PROXY_URL'] = proxy_url
    return env


def build_douban_proxy_url(settings: dict | None = None) -> str:
    settings = settings or {}
    return str(settings.get('crawler_proxy_url') or os.environ.get('CRAWLER_PROXY_URL') or '').strip()


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
        ], env=build_crawler_env(settings))
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


async def run_douban_backfill_job(force: bool = False) -> dict:
    if _douban_backfill_lock.locked() and not force:
        return {'started': False, 'reason': 'douban backfill job already running'}

    async with _douban_backfill_lock:
        db = get_db()
        settings = await get_admin_settings()
        started_at = datetime.utcnow()
        await _update_backfill_status({
            'last_douban_backfill_started_at': started_at,
            'last_douban_backfill_finished_at': None,
            'last_douban_backfill_status': 'running',
            'last_douban_backfill_output': 'douban backfill started',
        })

        limit = max(int(settings.get('douban_backfill_limit') or 50), 1)
        search_url = str(settings.get('douban_search_url') or 'https://s.stdlang.com/search').strip()
        timeout = max(int(settings.get('douban_backfill_timeout_seconds') or 20), 5)
        proxy_url = build_douban_proxy_url(settings)

        cursor = db['anime'].find(
            {
                '$or': [
                    {'poster_local': {'$in': [None, '']}},
                    {'poster_local': {'$exists': False}},
                ],
                'title': {'$type': 'string', '$ne': ''},
            },
            {'title': 1, 'year': 1, 'poster_url': 1, 'poster_local': 1, 'director': 1, 'synopsis': 1, 'voice_actors': 1, 'genres': 1},
        ).sort([('updated_at', -1), ('discovered_at', -1)]).limit(limit)

        outputs: list[str] = []
        matched = 0
        updated = 0
        failed = 0

        async for doc in cursor:
            title = str(doc.get('title') or '').strip()
            year = doc.get('year')
            if not title:
                continue

            search_result = search_douban_subject_url(title, year, search_url=search_url, proxy_url=proxy_url)
            if not search_result:
                outputs.append(f"[skip] {title} -> no douban result")
                continue

            matched += 1
            subject_url = search_result['url']
            outputs.append(f"[match] {title} -> {subject_url}")

            try:
                detail = fetch_douban_subject_metadata(subject_url, timeout=timeout, proxy_url=proxy_url)
                metadata = detail.get('metadata') or {}
                poster_url = metadata.get('poster_url') or doc.get('poster_url')
                poster_local = doc.get('poster_local')
                if poster_url and not poster_local:
                    poster_local = download_poster(
                        poster_url,
                        str(doc.get('_id') or '').replace('ObjectId(', '').replace(')', '') or title,
                    )

                update_data = {}
                for field in ('title', 'original_title', 'year', 'director', 'synopsis', 'voice_actors', 'genres'):
                    new_value = metadata.get(field)
                    old_value = doc.get(field)
                    if new_value and not old_value:
                        update_data[field] = new_value
                if poster_url and not doc.get('poster_url'):
                    update_data['poster_url'] = poster_url
                if poster_local and not doc.get('poster_local'):
                    update_data['poster_local'] = poster_local
                if subject_url not in (doc.get('source_urls') or []):
                    update_data['source_urls'] = (doc.get('source_urls') or []) + [subject_url]
                if update_data:
                    update_data['updated_at'] = datetime.utcnow()
                    await db['anime'].update_one({'_id': doc['_id']}, {'$set': update_data})
                    updated += 1
                    outputs.append(f"[update] {title} -> {', '.join(update_data.keys())}")
                else:
                    outputs.append(f"[noop] {title}")
            except Exception as exc:
                failed += 1
                outputs.append(f"[error] {title} -> {exc}")

        finished_at = datetime.utcnow()
        status = 'success' if failed == 0 else ('partial' if updated else 'failed')
        await _update_backfill_status({
            'last_douban_backfill_started_at': started_at,
            'last_douban_backfill_finished_at': finished_at,
            'last_douban_backfill_status': status,
            'last_douban_backfill_output': '\n'.join(outputs)[-4000:] if outputs else None,
        })
        return {
            'started': True,
            'status': status,
            'matched': matched,
            'updated': updated,
            'failed': failed,
            'output': '\n'.join(outputs)[-4000:] if outputs else '',
        }


def is_douban_backfill_running() -> bool:
    return _douban_backfill_lock.locked() or (_douban_backfill_task is not None and not _douban_backfill_task.done())


async def start_douban_backfill_job(force: bool = False) -> dict:
    global _douban_backfill_task

    if is_douban_backfill_running() and not force:
        return {'started': False, 'reason': 'douban backfill job already running'}

    db = get_db()
    started_at = datetime.utcnow()
    if db is not None:
        await _update_backfill_status({
            'last_douban_backfill_started_at': started_at,
            'last_douban_backfill_finished_at': None,
            'last_douban_backfill_status': 'running',
            'last_douban_backfill_output': 'douban backfill queued in FastAPI background task',
        })

    async def runner():
        try:
            await run_douban_backfill_job(force=True)
        except asyncio.CancelledError:
            db = get_db()
            if db is not None:
                now = datetime.utcnow()
                await _update_backfill_status({
                    'last_douban_backfill_started_at': started_at,
                    'last_douban_backfill_finished_at': now,
                    'last_douban_backfill_status': 'cancelled',
                    'last_douban_backfill_output': 'douban backfill task cancelled',
                })
            raise
        except Exception as exc:
            logger.exception('[Scheduler] douban backfill task failed: %s', exc)
            db = get_db()
            if db is not None:
                now = datetime.utcnow()
                await _update_backfill_status({
                    'last_douban_backfill_started_at': started_at,
                    'last_douban_backfill_finished_at': now,
                    'last_douban_backfill_status': 'failed',
                    'last_douban_backfill_output': str(exc)[-4000:],
                })

    _douban_backfill_task = asyncio.create_task(runner(), name='douban-backfill-job')
    return {'started': True, 'status': 'running', 'mode': 'background', 'started_at': started_at}


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
        parsed = urlparse(domain if '://' in domain else f'https://{domain}')
        host = parsed.netloc or parsed.path
        if host:
            push(f'https://{host}')
            push(f'http://{host}')

    return urls


def build_search_url(template: str, title: str) -> str | None:
    normalized_template = str(template or '').strip()
    normalized_title = str(title or '').strip()
    if not normalized_template or not normalized_title:
        return None

    encoded_title = quote_plus(normalized_title)
    if '{query}' in normalized_template:
        return normalized_template.replace('{query}', encoded_title)
    if '{title}' in normalized_template:
        return normalized_template.replace('{title}', encoded_title)
    return f'{normalized_template}{encoded_title}'


async def build_source_search_targets(source: dict) -> list[str]:
    template = str(source.get('search_url_template') or '').strip()
    if not template:
        return []

    db = get_db()
    limit = min(max(int(source.get('search_title_limit') or 50), 1), 1000)
    seen_titles: set[str] = set()
    targets: list[str] = []
    cursor = (
        db['anime']
        .find({'title': {'$type': 'string', '$ne': ''}}, {'title': 1, 'updated_at': 1, 'discovered_at': 1})
        .sort([('updated_at', -1), ('discovered_at', -1)])
        .limit(limit * 3)
    )

    async for doc in cursor:
        title = str(doc.get('title') or '').strip()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        url = build_search_url(template, title)
        if url:
            targets.append(url)
        if len(targets) >= limit:
            break

    return targets


def build_search_crawl_args(source: dict, target: str) -> list[str]:
    raw_max_pages = source.get('search_pagination_max_pages')
    max_pages = int(raw_max_pages if raw_max_pages is not None else 200)
    return [
        'crawl',
        '-u', target,
        '--search-discovery',
        '--max-depth', str(100000 if max_pages == 0 else max_pages + 1),
        '--search-pagination-max-pages', str(max_pages),
    ]


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

    task = await spawn_backend_command(args, env=build_crawler_env(await get_admin_settings()))
    return task


def is_source_crawl_running(source_id: str) -> bool:
    task = _source_crawl_tasks.get(source_id)
    return bool(task and not task.done())


async def start_source_crawl_job(source: dict, force: bool = False) -> dict[str, Any]:
    db = get_db()
    source_id = str(source['_id'])

    if is_source_crawl_running(source_id) and not force:
        return {'started': False, 'reason': 'source crawl already running'}

    args = ['crawl', '--max-depth', str(int(source.get('max_depth') or 3))]
    seed_url = str(source.get('seed_url') or '').strip()
    domain = str(source.get('domain') or '').strip()

    if seed_url:
        args.extend(['-u', seed_url])
    elif domain:
        args.extend(['-d', domain])
    else:
        raise ValueError('source missing domain/seed_url')

    started_at = datetime.utcnow()
    await db['crawl_sources'].update_one(
        {'_id': source['_id']},
        {'$set': {
            'last_run_at': started_at,
            'last_run_status': 'running',
            'last_run_output': f"running args={' '.join(args)}",
            'updated_at': started_at,
        }}
    )

    settings = await get_admin_settings()

    async def runner():
        try:
            code, output = await run_backend_command_stream(args, env=build_crawler_env(settings))
            finished_at = datetime.utcnow()
            status = 'success' if code == 0 else 'failed'
            await db['crawl_sources'].update_one(
                {'_id': source['_id']},
                {'$set': {
                    'last_run_at': finished_at,
                    'last_run_status': status,
                    'last_run_output': output[-4000:] if output else f'process exited with code={code}',
                    'updated_at': finished_at,
                }}
            )
        except asyncio.CancelledError:
            finished_at = datetime.utcnow()
            await db['crawl_sources'].update_one(
                {'_id': source['_id']},
                {'$set': {
                    'last_run_at': finished_at,
                    'last_run_status': 'cancelled',
                    'last_run_output': 'source crawl task cancelled',
                    'updated_at': finished_at,
                }}
            )
            raise
        except Exception as exc:
            logger.exception('[Scheduler] source crawl task failed: %s', exc)
            finished_at = datetime.utcnow()
            await db['crawl_sources'].update_one(
                {'_id': source['_id']},
                {'$set': {
                    'last_run_at': finished_at,
                    'last_run_status': 'failed',
                    'last_run_output': str(exc)[-4000:],
                    'updated_at': finished_at,
                }}
            )
        finally:
            _source_crawl_tasks.pop(source_id, None)

    _source_crawl_tasks[source_id] = asyncio.create_task(runner(), name=f'source-crawl:{source_id}')
    return {
        'started': True,
        'status': 'running',
        'mode': 'background',
        'source_id': source_id,
        'started_at': started_at,
    }


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
                'last_source_discovery_output': 'source discovery started; loading enabled sources...',
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
            search_targets = await build_source_search_targets(source)
            for target in search_targets:
                if target not in targets:
                    targets.append(target)
            if not targets:
                outputs.append(f"[{source.get('name')}] skipped: no discovery targets")
                continue

            source_max_depth = min(int(source.get('discovery_max_depth') or max_depth_default), 20)
            source_failures = 0
            source_outputs: list[str] = []
            source_header = (
                f"[{source.get('name')}] discovery targets={len(targets)}, "
                f"entry_targets={len(targets) - len(search_targets)}, "
                f"search_targets={len(search_targets)}, depth={source_max_depth}"
            )
            outputs.append(source_header)
            source_outputs.append(source_header)
            await db['crawl_sources'].update_one(
                {'_id': source['_id']},
                {'$set': {
                    'last_discovery_at': datetime.utcnow(),
                    'last_discovery_status': 'running',
                    'last_discovery_output': source_header,
                    'updated_at': datetime.utcnow(),
                }}
            )

            for target in targets:
                is_search_target = target in search_targets
                args = build_search_crawl_args(source, target) if is_search_target else ['crawl', '-u', target, '--max-depth', str(source_max_depth)]
                mode = 'search' if is_search_target else 'entry'
                current_line = f"[{source.get('name')}] running {mode}: {target}\nargs={' '.join(args)}"
                await db['app_settings'].update_one(
                    {'_id': 'admin'},
                    {'$set': {
                        'last_source_discovery_status': 'running',
                        'last_source_discovery_output': '\n\n'.join([*outputs, current_line])[-4000:],
                        'updated_at': datetime.utcnow(),
                    }}
                )
                await db['crawl_sources'].update_one(
                    {'_id': source['_id']},
                    {'$set': {
                        'last_discovery_status': 'running',
                        'last_discovery_output': '\n\n'.join([*source_outputs, current_line])[-4000:],
                        'updated_at': datetime.utcnow(),
                    }}
                )
                code, output = await run_backend_command(args, env=build_crawler_env(settings))
                started += 1
                if code != 0:
                    failures += 1
                    source_failures += 1
                compact = f"[{source.get('name')}] {mode} {target} -> code={code}"
                if output.strip():
                    compact += f"\n{output[-800:]}"
                outputs.append(compact)
                source_outputs.append(compact)

            await db['crawl_sources'].update_one(
                {'_id': source['_id']},
                {'$set': {
                    'last_discovery_at': datetime.utcnow(),
                    'last_discovery_status': 'success' if source_failures == 0 else 'partial',
                    'last_discovery_output': '\n\n'.join(source_outputs)[-4000:],
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

    db = get_db()
    started_at = datetime.utcnow()
    if db is not None:
        await db['app_settings'].update_one(
            {'_id': 'admin'},
            {'$set': {
                'last_source_discovery_started_at': started_at,
                'last_source_discovery_finished_at': None,
                'last_source_discovery_status': 'running',
                'last_source_discovery_output': 'source discovery queued in FastAPI background task',
                'updated_at': started_at,
            }}
        )

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
                        'last_source_discovery_output': (
                            'source discovery task cancelled; usually caused by backend shutdown/restart '
                            'while the in-process background task was running'
                        ),
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
    return {'started': True, 'status': 'running', 'mode': 'background', 'started_at': started_at}


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
            if settings.get('douban_backfill_enabled'):
                interval = max(int(settings.get('douban_backfill_interval_minutes') or 60), 5)
                last_started = settings.get('last_douban_backfill_started_at')
                now = datetime.utcnow()
                due = True
                if last_started:
                    due = (now - last_started).total_seconds() >= interval * 60
                if due and not is_douban_backfill_running():
                    logger.info('[Scheduler] running douban backfill job')
                    await start_douban_backfill_job()
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
    global _scheduler_task, _source_discovery_task, _douban_backfill_task
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
    if _douban_backfill_task and not _douban_backfill_task.done():
        _douban_backfill_task.cancel()
        try:
            await _douban_backfill_task
        except asyncio.CancelledError:
            pass
    _douban_backfill_task = None
    for task in list(_source_crawl_tasks.values()):
        if not task.done():
            task.cancel()
    for task in list(_source_crawl_tasks.values()):
        try:
            await task
        except asyncio.CancelledError:
            pass
    _source_crawl_tasks.clear()
