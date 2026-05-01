"""MongoDB 连接管理"""

from datetime import datetime

import pymongo
from scrapy.utils.project import get_project_settings


class MongoDB:
    """MongoDB 连接管理器"""

    _client = None
    _db = None

    @classmethod
    def get_client(cls):
        if cls._client is None:
            settings = get_project_settings()
            cls._client = pymongo.MongoClient(settings.get('MONGODB_URI', 'mongodb://localhost:27017'))
        return cls._client

    @classmethod
    def get_db(cls):
        if cls._db is None:
            settings = get_project_settings()
            client = cls.get_client()
            cls._db = client[settings.get('MONGODB_DB', 'anime_db')]
        return cls._db

    @classmethod
    def get_anime_collection(cls):
        settings = get_project_settings()
        collection_name = settings.get('MONGODB_ANIME_COLLECTION', 'anime')
        return cls.get_db()[collection_name]

    @classmethod
    def get_domain_collection(cls):
        settings = get_project_settings()
        collection_name = settings.get('MONGODB_DOMAIN_COLLECTION', 'discovered_domains')
        return cls.get_db()[collection_name]

    @classmethod
    def ensure_indexes(cls):
        """创建必要的索引"""
        anime_col = cls.get_anime_collection()
        domain_col = cls.get_domain_collection()

        # 动画集合索引
        anime_col.create_index('dedup_key', unique=True)
        anime_col.create_index('title')
        anime_col.create_index('year')
        anime_col.create_index('director')
        anime_col.create_index('genres')
        anime_col.create_index('source_domain')
        anime_col.create_index('play_sources.domain')
        anime_col.create_index([('year', -1), ('discovered_at', -1)])
        anime_col.create_index('discovered_at')

        # 域名集合索引
        domain_col.create_index('domain', unique=True)
        domain_col.create_index('status')
        domain_col.create_index('is_anime_site')
        domain_col.create_index([('is_anime_site', 1), ('status', 1)])

        print('[MongoDB] 索引创建完成')

    @classmethod
    def close(cls):
        if cls._client:
            cls._client.close()
            cls._client = None
            cls._db = None

    @classmethod
    def update_domain_status(cls, domain, status, **extra):
        """更新域名状态。"""
        if not domain:
            return

        data = {
            'status': status,
            'updated_at': datetime.now(),
        }
        data.update(extra)

        cls.get_domain_collection().update_one(
            {'domain': domain.lower()},
            {'$set': data},
            upsert=False,
        )

    @classmethod
    def get_domain(cls, domain):
        if not domain:
            return None
        return cls.get_domain_collection().find_one({'domain': domain.lower()})
