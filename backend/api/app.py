"""FastAPI 应用入口"""

import asyncio
import os
import secrets
import sys
import time
from collections import defaultdict, deque
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager
from config.env import load_backend_env
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

load_backend_env()

from api.database import connect, close
from api.routes import admin, anime, domains, stats
from api.scheduler import start_scheduler, stop_scheduler

RATE_LIMIT_MAX_REQUESTS = max(int(os.environ.get('PUBLIC_API_RATE_LIMIT_PER_MINUTE', '60') or 60), 1)
RATE_LIMIT_WINDOW_SECONDS = 60.0
_rate_limit_buckets: dict[str, deque[float]] = defaultdict(deque)
_rate_limit_lock = asyncio.Lock()


def has_internal_api_key(request: Request) -> bool:
    internal_api_key = os.environ.get('INTERNAL_API_KEY', '').strip()
    provided_api_key = request.headers.get('x-api-key', '').strip()
    return bool(internal_api_key and secrets.compare_digest(provided_api_key, internal_api_key))


def rate_limit_key(request: Request) -> str:
    forwarded_for = request.headers.get('x-forwarded-for', '').split(',')[0].strip()
    if forwarded_for:
        return forwarded_for
    if request.client and request.client.host:
        return request.client.host
    return 'unknown-client'


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect()
    await start_scheduler()
    yield
    await stop_scheduler()
    await close()


app = FastAPI(
    title='动漫爬虫 API',
    description='动漫资源搜索引擎 - 动画列表、详情、播放源、域名管理接口',
    version='1.0.0',
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=False,
    allow_methods=['GET'],
    allow_headers=['*'],
)


@app.middleware('http')
async def public_rate_limit_middleware(request: Request, call_next):
    if (
        request.method == 'GET'
        and not request.url.path.startswith('/api/admin')
        and not has_internal_api_key(request)
    ):
        key = rate_limit_key(request)
        now = time.monotonic()
        async with _rate_limit_lock:
            bucket = _rate_limit_buckets[key]
            while bucket and now - bucket[0] >= RATE_LIMIT_WINDOW_SECONDS:
                bucket.popleft()
            if len(bucket) >= RATE_LIMIT_MAX_REQUESTS:
                return JSONResponse(
                    status_code=429,
                    content={'detail': '请求过于频繁，请稍后再试'},
                )
            bucket.append(now)
    return await call_next(request)

app.include_router(anime.router)
app.include_router(domains.router)
app.include_router(stats.router)
app.include_router(admin.router)

poster_dir = Path(__file__).resolve().parents[1] / 'posters'
if poster_dir.exists():
    app.mount('/posters', StaticFiles(directory=str(poster_dir)), name='posters')


@app.get('/')
async def root():
    return {
        'name': '动漫爬虫 API',
        'version': '1.0.0',
        'docs': '/docs',
    }


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('api.app:app', host='0.0.0.0', port=8000, reload=True)
