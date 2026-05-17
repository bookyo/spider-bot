"""MongoDB 异步连接管理"""

import os
from motor.motor_asyncio import AsyncIOMotorClient
from config.env import load_backend_env

load_backend_env()

MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017')
MONGODB_DB = os.environ.get('MONGODB_DB', 'anime_db')

client: AsyncIOMotorClient = None
db = None


async def connect():
    global client, db
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[MONGODB_DB]
    await db['crawl_sources'].create_index('created_at')
    await db['crawl_sources'].create_index('enabled')
    await db['crawl_sources'].create_index('domain')
    await db['app_settings'].create_index('updated_at')

    # 采集源相关集合索引
    await db['collect_sources'].create_index('url')
    await db['collect_sources'].create_index('mid')
    await db['collect_sources'].create_index('status')
    await db['collect_sources'].create_index('updated_at')

    await db['collect_tasks'].create_index([('collect_source', 1), ('created_at', -1)])
    await db['collect_tasks'].create_index([('status', 1), ('created_at', -1)])

    await db['collect_history'].create_index('url_hash', unique=True)
    await db['collect_history'].create_index('created_at')

    await db['collect_type_bindings'].create_index(
        [('collect_source', 1), ('source_type_id', 1)], unique=True
    )


async def close():
    global client
    if client:
        client.close()


def get_db():
    return db
