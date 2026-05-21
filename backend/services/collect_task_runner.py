"""采集任务执行器 - 队列管理与异步执行"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId

from api.database import get_db
from services.collect_engine import collect_engine, build_collect_run_options

logger = logging.getLogger(__name__)

# 任务心跳超时（10分钟）
DEFAULT_TASK_STALE_MS = 10 * 60 * 1000
MAX_TASK_LOGS = 40

COLLECT_RANGE_LABELS: dict[str, str] = {
    'today': '今日更新',
    '1day': '1日内更新',
    '2day': '2日内更新',
    'week': '本周更新',
    'month': '30日内更新',
    '3month': '90日内更新',
    'all': '全量采集',
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _build_pending_message(position: int, active_name: str = '') -> str:
    if position > 0:
        queue_text = f'队列第 {position} 位'
    else:
        queue_text = '等待执行'
    if active_name:
        return f'{queue_text}，当前执行 {active_name}'
    return queue_text


class CollectTaskRunner:
    """采集任务执行器 - 管理任务队列和进度"""

    def __init__(self):
        self.queue: list[str] = []          # 等待中的任务 ID
        self.running = False
        self.active_task_id: Optional[str] = None
        self.active_source_name = ''
        self._lock = asyncio.Lock()

    async def start(self):
        """启动时清理遗留任务并恢复为空闲状态。"""
        await self.recover_stale_tasks()

    async def enqueue(
        self,
        source_id: str,
        range_type: str = 'today',
        trigger: str = 'manual',
    ) -> dict[str, Any]:
        """将采集源加入任务队列"""
        db = get_db()
        if db is None:
            raise RuntimeError('数据库未连接')

        try:
            oid = ObjectId(source_id)
        except Exception:
            raise ValueError('无效的 source_id')

        source = await db['collect_sources'].find_one({'_id': oid})
        if not source:
            raise ValueError('采集源未找到')
        if not source.get('status', True):
            raise ValueError('采集源已禁用')

        normalized = build_collect_run_options({'range': range_type, 'type': range_type})
        range_key = normalized['type']

        # 检查是否已有运行中/等待中的任务
        existing = await db['collect_tasks'].find_one({
            'collect_source': oid,
            'status': {'$in': ['pending', 'running']},
        }, sort=[('created_at', -1)])

        if existing:
            source_name = str(source.get('name', '')).strip()
            status_label = '正在执行' if existing.get('status') == 'running' else '在队列中'
            msg = f'已有相同采集任务{status_label}' if not source_name else f'{source_name} 已有任务{status_label}'
            return {
                **existing,
                '_id': str(existing['_id']),
                'reused_existing': True,
                'enqueue_message': msg,
            }

        async with self._lock:
            position = len(self.queue) + (1 if self.running else 0) + 1

        now = _now()
        source_name = str(source.get('name', '')).strip()
        range_label = COLLECT_RANGE_LABELS.get(range_key, range_key)

        doc = {
            'collect_source': oid,
            'source_name': source_name,
            'range': range_key,
            'trigger': trigger,
            'active_key': str(source_id),
            'status': 'pending',
            'queue_position': position,
            'processed': 0,
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'pages': 0,
            'current_name': '',
            'message': _build_pending_message(position, self.active_source_name),
            'heartbeat_at': now,
            'started_at': None,
            'finished_at': None,
            'logs': [{
                'at': now,
                'text': f'任务已创建，等待执行 {range_label}',
            }],
            'result': None,
            'created_at': now,
            'updated_at': now,
        }

        try:
            result = await db['collect_tasks'].insert_one(doc)
        except Exception as e:
            # 重复键冲突 → 重试查找
            if 'duplicate' in str(e).lower() or '11000' in str(e):
                dup = await db['collect_tasks'].find_one({
                    'active_key': str(source_id),
                    'status': {'$in': ['pending', 'running']},
                }, sort=[('created_at', -1)])
                if dup:
                    return {
                        **dup,
                        '_id': str(dup['_id']),
                        'reused_existing': True,
                        'enqueue_message': '已有相同采集任务正在执行或等待中',
                    }
            raise

        task_id = str(result.inserted_id)
        doc['_id'] = task_id

        async with self._lock:
            self.queue.append(task_id)

        await self._refresh_pending_messages()

        # 启动队列处理
        asyncio.create_task(self._process_queue())

        return doc

    async def enqueue_for_all_sources(
        self,
        range_type: str = 'today',
        trigger: str = 'scheduler',
    ) -> list[dict[str, Any]]:
        """为所有启用的采集源入队"""
        db = get_db()
        if db is None:
            return []

        sources = await db['collect_sources'].find({
            'status': True,
            'mid': 1,
        }).to_list(None)

        tasks = []
        for source in sources:
            try:
                task = await self.enqueue(
                    source_id=str(source['_id']),
                    range_type=range_type,
                    trigger=trigger,
                )
                tasks.append(task)
            except Exception as e:
                logger.error(f'入队采集源 {source.get("name", "")} 失败: {e}')

        return tasks

    async def get_task(self, task_id: str) -> Optional[dict]:
        await self._fail_stale_tasks()
        db = get_db()
        if db is None:
            return None
        try:
            doc = await db['collect_tasks'].find_one({'_id': ObjectId(task_id)})
        except Exception:
            return None
        if doc:
            doc['_id'] = str(doc['_id'])
            if doc.get('collect_source'):
                doc['collect_source'] = str(doc['collect_source'])
        return doc

    async def list_recent(self, limit: int = 20) -> list[dict]:
        db = get_db()
        if db is None:
            return []
        cursor = db['collect_tasks'].find().sort('created_at', -1).limit(limit)
        docs = await cursor.to_list(None)
        for doc in docs:
            doc['_id'] = str(doc['_id'])
            if doc.get('collect_source'):
                doc['collect_source'] = str(doc['collect_source'])
        return docs

    async def recover_stale_tasks(self):
        """服务重启时恢复中断的任务"""
        db = get_db()
        if db is None:
            return

        now = _now()
        await db['collect_tasks'].update_many(
            {'status': {'$in': ['pending', 'running']}},
            {'$set': {
                'active_key': None,
                'status': 'failed',
                'queue_position': 0,
                'heartbeat_at': now,
                'finished_at': now,
                'message': '服务重启，任务已中断，请重新发起采集',
            }},
        )

        async with self._lock:
            self.queue = []
            self.running = False
            self.active_task_id = None
            self.active_source_name = ''

    async def _fail_stale_tasks(self) -> int:
        """标记心跳超时的运行中任务为失败"""
        db = get_db()
        if db is None:
            return 0

        now = _now()
        cutoff = now.timestamp() * 1000 - DEFAULT_TASK_STALE_MS

        docs = await db['collect_tasks'].find({'status': 'running'}).to_list(None)
        stale = []
        for doc in docs:
            tid = str(doc['_id'])
            hb = doc.get('heartbeat_at')
            if hb and hb.timestamp() * 1000 < cutoff:
                stale.append(doc)

        if not stale:
            return 0

        stale_ids = [str(d['_id']) for d in stale]

        async with self._lock:
            if self.active_task_id in stale_ids:
                self.active_task_id = None
                self.active_source_name = ''
                self.running = False
            self.queue = [t for t in self.queue if t not in stale_ids]

        for doc in stale:
            await self._patch_task(
                str(doc['_id']),
                {
                    'active_key': None,
                    'status': 'failed',
                    'queue_position': 0,
                    'heartbeat_at': now,
                    'finished_at': now,
                    'message': '任务心跳超时，已自动终止，请重新发起采集',
                },
                '任务心跳超时，已自动终止',
            )

        await self._refresh_pending_messages()
        async with self._lock:
            should_restart = bool(self.queue) and not self.running
        if should_restart:
            asyncio.create_task(self._process_queue())
        return len(stale)

    async def _process_queue(self):
        """按顺序执行队列中的任务"""
        async with self._lock:
            if self.running:
                return
            self.running = True

        try:
            while True:
                async with self._lock:
                    if not self.queue:
                        break
                    task_id = self.queue.pop(0)
                    self.active_task_id = task_id

                await self._refresh_pending_messages()
                await self._run_task(task_id)
        finally:
            async with self._lock:
                self.active_task_id = None
                self.active_source_name = ''
                self.running = False
            await self._refresh_pending_messages()

    async def _run_task(self, task_id: str):
        """执行单个采集任务"""
        db = get_db()
        if db is None:
            return

        try:
            oid = ObjectId(task_id)
        except Exception:
            return

        task = await db['collect_tasks'].find_one({'_id': oid})
        if not task or task.get('status') in ('success', 'failed'):
            return

        self.active_source_name = str(task.get('source_name', '')).strip()

        await self._patch_task(
            task_id,
            {
                'status': 'running',
                'queue_position': 0,
                'heartbeat_at': _now(),
                'started_at': _now(),
                'finished_at': None,
                'message': '开始采集，准备拉取列表',
                'current_name': '',
                'processed': 0,
                'created': 0,
                'updated': 0,
                'skipped': 0,
                'pages': 0,
            },
            '开始采集，准备拉取列表',
        )

        collect_source_id = task.get('collect_source')
        if collect_source_id is None:
            await self._patch_task(task_id, {
                'active_key': None,
                'status': 'failed',
                'finished_at': _now(),
                'message': '采集源不存在',
            }, '采集源不存在')
            return

        source = await db['collect_sources'].find_one({'_id': collect_source_id})
        if not source:
            await self._patch_task(task_id, {
                'active_key': None,
                'status': 'failed',
                'finished_at': _now(),
                'message': '采集源不存在',
            }, '采集源不存在')
            return

        try:
            result = await collect_engine.run(
                source=source,
                range_type=task.get('range', 'today'),
                on_status=self._make_status_handler(task_id),
                on_progress=self._make_progress_handler(task_id),
            )

            await self._patch_task(
                task_id,
                {
                    'active_key': None,
                    'status': 'success',
                    'heartbeat_at': _now(),
                    'finished_at': _now(),
                    'processed': result.get('processed', 0),
                    'created': result.get('created', 0),
                    'updated': result.get('updated', 0),
                    'skipped': result.get('skipped', 0),
                    'pages': result.get('pages', 0),
                    'result': result,
                    'message': f"采集完成：新增 {result.get('created', 0)}，更新 {result.get('updated', 0)}",
                },
                f"采集完成：新增 {result.get('created', 0)}，更新 {result.get('updated', 0)}",
            )

        except Exception as e:
            logger.error(f'采集任务 {task_id} 失败: {e}')
            await self._patch_task(
                task_id,
                {
                    'active_key': None,
                    'status': 'failed',
                    'heartbeat_at': _now(),
                    'finished_at': _now(),
                    'message': str(e) or '采集失败',
                },
                str(e) or '采集失败',
            )
        finally:
            self.active_source_name = ''

    def _make_status_handler(self, task_id: str):
        async def handler(status: dict[str, Any]):
            await self._patch_task(
                task_id,
                {
                    'heartbeat_at': _now(),
                    'message': status.get('message', '采集中'),
                    'current_name': status.get('current_name', ''),
                },
                status.get('log') or status.get('message', ''),
            )
        return handler

    def _make_progress_handler(self, task_id: str):
        async def handler(progress: dict[str, Any]):
            action = progress.get('action', '')
            label = '更新' if action == 'updated' else '新增'
            current_name = progress.get('current_name', '')
            msg = f'{label}：{current_name}' if current_name else f'{label}'

            await self._patch_task(
                task_id,
                {
                    'heartbeat_at': _now(),
                    'processed': progress.get('processed', 0),
                    'created': progress.get('created', 0),
                    'updated': progress.get('updated', 0),
                    'skipped': progress.get('skipped', 0),
                    'pages': progress.get('page', 0),
                    'current_name': current_name,
                    'message': msg,
                },
            )
        return handler

    async def _patch_task(self, task_id: str, set_fields: dict[str, Any], log_text: str = ''):
        db = get_db()
        if db is None:
            return
        try:
            oid = ObjectId(task_id)
        except Exception:
            return

        update: dict[str, Any] = {'$set': {**set_fields, 'updated_at': _now()}}
        if log_text:
            update['$push'] = {
                'logs': {
                    '$each': [{'at': _now(), 'text': str(log_text).strip()}],
                    '$slice': -MAX_TASK_LOGS,
                },
            }

        await db['collect_tasks'].update_one({'_id': oid}, update)

    async def _refresh_pending_messages(self):
        """刷新等待中任务的排队信息"""
        db = get_db()
        if db is None:
            return

        now = _now()
        tasks_to_update = []
        async with self._lock:
            for idx, tid in enumerate(self.queue):
                tasks_to_update.append((tid, idx + 1))

        for tid, pos in tasks_to_update:
            try:
                oid = ObjectId(tid)
                await db['collect_tasks'].update_one(
                    {'_id': oid},
                    {'$set': {
                        'queue_position': pos,
                        'heartbeat_at': now,
                        'message': _build_pending_message(pos, self.active_source_name),
                    }},
                )
            except Exception:
                pass


# 导出单例
collect_task_runner = CollectTaskRunner()
