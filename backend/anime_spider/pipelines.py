"""数据管道 - 去重、数据补全、海报下载、MongoDB 存储"""

import logging
from datetime import datetime

import pymongo
from scrapy.utils.project import get_project_settings

from anime_spider.items import AnimeItem, DomainItem
from anime_spider.utils.crawl_metrics import CrawlMetrics
from anime_spider.utils.dedup import (
    extract_season_marker,
    generate_anime_dedup_key,
    generate_title_aliases,
    merge_play_sources,
    normalize_person_name,
    normalize_play_sources_for_storage,
    normalize_title,
    summarize_play_sources,
)
from anime_spider.utils.poster import download_poster

logger = logging.getLogger(__name__)

# 可补全的字段（新数据有值且旧数据为空时更新）
ENRICHABLE_FIELDS = [
    'title',
    'director',
    'year',
    'original_title',
    'synopsis',
    'voice_actors',
    'genres',
]


class AnimePipeline:
    """动画数据管道

    功能:
    - 去重：title + year + director
    - 播放源合并：按域名去重，合并分集
    - 数据补全：从后续爬取中填充缺失字段
    - 海报下载：下载竖屏海报到本地
    """

    def __init__(self):
        self.client = None
        self.db = None
        self.anime_col = None
        self.domain_col = None
        self.poster_dir = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def open_spider(self, spider):
        """爬虫启动时连接 MongoDB"""
        settings = get_project_settings()
        uri = settings.get('MONGODB_URI', 'mongodb://localhost:27017')
        db_name = settings.get('MONGODB_DB', 'anime_db')

        self.client = pymongo.MongoClient(uri)
        self.db = self.client[db_name]
        self.anime_col = self.db[settings.get('MONGODB_ANIME_COLLECTION', 'anime')]
        self.domain_col = self.db[settings.get('MONGODB_DOMAIN_COLLECTION', 'discovered_domains')]
        self.poster_dir = settings.get('POSTER_DIR', 'posters')

        self._ensure_indexes()

        logger.info(f'[Pipeline] MongoDB 连接成功: {db_name}')

    def close_spider(self, spider):
        """爬虫关闭时断开连接"""
        if self.client:
            self.client.close()
            logger.info('[Pipeline] MongoDB 连接关闭')

    def process_item(self, item, spider):
        """处理数据项"""
        if isinstance(item, AnimeItem):
            return self._process_anime(item, spider)
        elif isinstance(item, DomainItem):
            return self._process_domain(item, spider)
        return item

    def _process_anime(self, item, spider):
        """处理动画数据：去重、补全、海报下载"""
        dedup_key = item.get('dedup_key')
        if not dedup_key:
            dedup_key = generate_anime_dedup_key(
                item.get('title'),
                item.get('year'),
                item.get('director'),
            )

        item['normalized_title'] = normalize_title(item.get('title'))
        item['aliases'] = generate_title_aliases(
            item.get('title'),
            item.get('original_title'),
        )
        anime_key = self._extract_anime_key_from_item(item)
        if item.get('play_sources'):
            item['play_sources'] = normalize_play_sources_for_storage(
                item.get('play_sources', []),
                anime_key=anime_key,
            )

        try:
            existing = self._find_existing_anime(item, dedup_key)
            if existing:
                self._normalize_existing_sources(existing)

            if existing:
                self._update_existing(existing, item, dedup_key)
            else:
                if self._is_follow_only_item(item):
                    logger.info(
                        '[Pipeline] 跳过孤立补源项: extractor=%s source_url=%s dedup_key=%s',
                        item.get('extractor_name'),
                        item.get('source_url'),
                        dedup_key,
                    )
                    return item
                self._insert_new(item, dedup_key)

        except pymongo.errors.DuplicateKeyError:
            logger.debug(f'[Pipeline] 重复键冲突: {dedup_key}')
        except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure) as e:
            logger.error(f'[Pipeline] MongoDB 错误: {e}')
            raise

        return item

    def _is_follow_only_item(self, item):
        extractor_name = item.get('extractor_name')
        if extractor_name not in {'play_page_follow', 'iframe_follow'}:
            return False
        return not bool(item.get('title'))

    def _extract_anime_key_from_item(self, item):
        for value in [item.get('source_url'), *(item.get('source_urls') or [])]:
            if not value:
                continue
            import re
            match = re.search(r'/(?:post|play)/(\d+)', str(value))
            if match:
                return match.group(1)
        return None

    def _normalize_existing_sources(self, existing):
        anime_key = self._extract_anime_key_from_item(existing) or self._extract_anime_key_from_existing_sources(existing)
        current_sources = existing.get('play_sources', []) or []
        normalized_sources = normalize_play_sources_for_storage(current_sources, anime_key=anime_key)

        if not self._sources_changed(current_sources, normalized_sources):
            return

        summary = summarize_play_sources(normalized_sources)
        existing['play_sources'] = normalized_sources
        existing['latest_episode'] = summary['latest_episode']
        existing['total_episode_count'] = summary['total_episode_count']
        self.anime_col.update_one(
            {'_id': existing['_id']},
            {'$set': {
                'play_sources': normalized_sources,
                'latest_episode': summary['latest_episode'],
                'total_episode_count': summary['total_episode_count'],
            }}
        )

    def _extract_anime_key_from_existing_sources(self, existing):
        import re
        for source in existing.get('play_sources', []) or []:
            for value in [source.get('raw_url'), *[(ep or {}).get('url') for ep in source.get('episodes', [])[:3]]]:
                if not value:
                    continue
                match = re.search(r'/(?:post|play)/(\d+)', str(value))
                if match:
                    return match.group(1)
        return None

    def _update_existing(self, existing, item, dedup_key):
        """更新已存在的记录：合并播放源 + 补全缺失字段 + 下载海报"""
        update_data = {'updated_at': datetime.now()}
        enriched_fields = []

        # 1. 合并播放源
        current_sources = existing.get('play_sources', [])
        new_sources = item.get('play_sources', [])
        if new_sources:
            merged_sources = merge_play_sources(current_sources, new_sources)
            merged_sources = normalize_play_sources_for_storage(
                merged_sources,
                anime_key=self._extract_anime_key_from_item(item) or self._extract_anime_key_from_existing_sources(existing),
            )
            update_data['play_sources'] = merged_sources
            episode_summary = summarize_play_sources(merged_sources)
            update_data['latest_episode'] = episode_summary['latest_episode']
            update_data['total_episode_count'] = episode_summary['total_episode_count']
            update_data['new_episode_count'] = episode_summary['new_episode_count']
            update_data['incremental_found'] = episode_summary['new_episode_count'] > 0
            update_data['last_incremental_check'] = datetime.now()

        # 2. 补全缺失字段
        for field in ENRICHABLE_FIELDS:
            new_val = item.get(field)
            old_val = existing.get(field)
            if new_val and not old_val:
                update_data[field] = new_val
                enriched_fields.append(field)

        if item.get('normalized_title') and not existing.get('normalized_title'):
            update_data['normalized_title'] = item.get('normalized_title')
            enriched_fields.append('normalized_title')

        # 3. 来源 URL 追加
        source_url = item.get('source_url')
        if source_url and source_url not in existing.get('source_urls', []):
            update_data['source_urls'] = existing.get('source_urls', []) + [source_url]

        aliases = list(existing.get('aliases', []))
        for alias in item.get('aliases', []):
            if alias not in aliases:
                aliases.append(alias)
        if aliases:
            update_data['aliases'] = aliases[:20]

        if item.get('normalized_title'):
            update_data['normalized_title'] = item.get('normalized_title')

        # 4. 海报处理：如果本地没有海报且新数据有海报 URL
        poster_url = item.get('poster_url')
        has_local_poster = existing.get('poster_local')
        if poster_url and not has_local_poster:
            local_path = download_poster(poster_url, dedup_key, self.poster_dir)
            if local_path:
                update_data['poster_local'] = local_path
                update_data['poster_url'] = poster_url
                enriched_fields.append('poster_local')
            elif not existing.get('poster_url'):
                # 没有本地海报也没有远程 URL，先保存远程 URL
                update_data['poster_url'] = poster_url

        if len(update_data) > 1:  # 除了 updated_at 还有其他更新
            if item.get('extractor_name'):
                update_data['extractor_name'] = item.get('extractor_name')
            if item.get('extractor_confidence') is not None:
                update_data['extractor_confidence'] = item.get('extractor_confidence')
            if item.get('site_type'):
                update_data['site_type'] = item.get('site_type')
            update_data['quality_score'] = self._calculate_quality_score({
                **existing,
                **update_data,
            })
            self.anime_col.update_one(
                {'_id': existing['_id']},
                {'$set': update_data}
            )
            log_msg = f'[Pipeline] 补全动画: {item.get("title") or existing.get("title")}'
            if enriched_fields:
                log_msg += f' (补全: {", ".join(enriched_fields)})'
            if new_sources:
                log_msg += f' (播放源: {len(update_data.get("play_sources", []))})'
            logger.info(log_msg)

    def _sources_changed(self, current_sources, normalized_sources):
        if len(current_sources or []) != len(normalized_sources or []):
            return True

        def signature(source):
            episodes = tuple(
                (str((ep or {}).get('episode') or ''), str((ep or {}).get('url') or ''))
                for ep in source.get('episodes', [])
            )
            return (
                source.get('source_id'),
                source.get('provider_id'),
                source.get('source_name'),
                source.get('line_id'),
                source.get('anime_key'),
                episodes,
            )

        current_signatures = sorted(signature(source) for source in (current_sources or []))
        normalized_signatures = sorted(signature(source) for source in (normalized_sources or []))
        return current_signatures != normalized_signatures

    def _find_existing_anime(self, item, dedup_key):
        existing = self.anime_col.find_one({'dedup_key': dedup_key})
        if existing:
            return existing

        return self._find_existing_by_weak_match(item)

    def _find_existing_by_weak_match(self, item):
        normalized_title = item.get('normalized_title')
        aliases = [alias for alias in (item.get('aliases') or []) if alias]
        if not normalized_title and not aliases:
            return None

        candidate_query = {'$or': []}
        if normalized_title:
            candidate_query['$or'].append({'normalized_title': normalized_title})
        if aliases:
            candidate_query['$or'].append({'aliases': {'$in': aliases}})
        if not candidate_query['$or']:
            return None

        candidates = list(self.anime_col.find(candidate_query).limit(20))
        if not candidates:
            return None

        matched = []
        for candidate in candidates:
            score = self._score_weak_match(candidate, item)
            if score >= 100:
                matched.append((score, candidate))

        if not matched:
            return None

        matched.sort(key=lambda value: (value[0], value[1].get('quality_score', 0.0)), reverse=True)
        selected = matched[0][1]
        logger.info(
            '[Pipeline] 弱匹配归并: incoming=%s existing=%s existing_id=%s score=%s',
            item.get('title'),
            selected.get('title'),
            selected.get('_id'),
            matched[0][0],
        )
        return selected

    def _score_weak_match(self, existing, item):
        existing_title = existing.get('normalized_title') or normalize_title(existing.get('title'))
        incoming_title = item.get('normalized_title') or normalize_title(item.get('title'))
        if not existing_title or not incoming_title:
            return 0

        existing_season = extract_season_marker(existing_title)
        incoming_season = extract_season_marker(incoming_title)
        if self._season_value(existing_season) != self._season_value(incoming_season):
            return 0

        existing_aliases = set(existing.get('aliases') or [])
        if existing.get('title'):
            existing_aliases.update(generate_title_aliases(existing.get('title'), existing.get('original_title')))
        incoming_aliases = set(item.get('aliases') or [])

        score = 0
        if existing_title == incoming_title:
            score += 100
        elif incoming_aliases.intersection(existing_aliases):
            score += 85
        else:
            return 0

        year_score = self._compare_year(existing.get('year'), item.get('year'))
        if year_score < 0:
            return 0
        score += year_score

        director_score = self._compare_director(existing.get('director'), item.get('director'))
        if director_score < 0:
            return 0
        score += director_score

        return score

    def _season_value(self, season):
        if not season:
            return 1
        return season.get('value') or 1

    def _compare_year(self, left, right):
        if left and right:
            return 15 if str(left) == str(right) else -1
        if left or right:
            return 5
        return 0

    def _compare_director(self, left, right):
        left_normalized = normalize_person_name(left)
        right_normalized = normalize_person_name(right)
        if left_normalized and right_normalized:
            return 10 if left_normalized == right_normalized else -1
        if left_normalized or right_normalized:
            return 3
        return 0

    def _insert_new(self, item, dedup_key):
        """插入新记录，同时下载海报"""
        poster_url = item.get('poster_url')
        poster_local = None
        if poster_url:
            poster_local = download_poster(poster_url, dedup_key, self.poster_dir)

        doc = {
            'title': item.get('title'),
            'original_title': item.get('original_title'),
            'aliases': item.get('aliases', []),
            'normalized_title': item.get('normalized_title'),
            'year': item.get('year'),
            'director': item.get('director'),
            'voice_actors': item.get('voice_actors', []),
            'synopsis': item.get('synopsis'),
            'poster_url': poster_url,
            'poster_local': poster_local,
            'source_urls': [item.get('source_url')] if item.get('source_url') else [],
            'source_domain': item.get('source_domain'),
            'genres': item.get('genres', []),
            'play_sources': item.get('play_sources', []),
            'latest_episode': item.get('latest_episode'),
            'total_episode_count': item.get('total_episode_count'),
            'new_episode_count': item.get('new_episode_count', 0),
            'incremental_found': item.get('incremental_found', False),
            'last_incremental_check': item.get('last_incremental_check'),
            'incremental_priority': item.get('incremental_priority'),
            'dedup_key': dedup_key,
            'extractor_name': item.get('extractor_name'),
            'extractor_confidence': item.get('extractor_confidence'),
            'site_type': item.get('site_type'),
            'quality_score': self._calculate_quality_score(item),
            'discovered_at': datetime.now(),
            'updated_at': datetime.now(),
        }
        self.anime_col.insert_one(doc)
        logger.info(f'[Pipeline] 新增动画: {item.get("title")}')
        self._update_domain_metrics(item, crawl_succeeded=True)

    def _process_domain(self, item, spider):
        """处理域名数据"""
        domain = item.get('domain')
        if not domain:
            return item

        try:
            existing = self.domain_col.find_one({'domain': domain})

            if existing:
                update_data = {'updated_at': datetime.now()}
                if item.get('is_anime_site'):
                    update_data['is_anime_site'] = True
                if item.get('status'):
                    update_data['status'] = item.get('status')
                if item.get('site_type'):
                    update_data['site_type'] = item.get('site_type')
                if item.get('last_error') is not None:
                    update_data['last_error'] = item.get('last_error')
                if item.get('last_crawled'):
                    update_data['last_crawled'] = item.get('last_crawled')
                if item.get('retry_count') is not None:
                    update_data['retry_count'] = item.get('retry_count')
                for field in [
                    'priority_score', 'total_crawls', 'success_crawls', 'success_rate',
                    'total_anime_found', 'avg_quality_score', 'health_score',
                ]:
                    if item.get(field) is not None:
                        update_data[field] = item.get(field)
                self.domain_col.update_one(
                    {'_id': existing['_id']},
                    {'$set': update_data}
                )
            else:
                doc = {
                    'domain': domain,
                    'source': item.get('source', 'unknown'),
                    'discovered_at': datetime.now(),
                    'is_anime_site': item.get('is_anime_site', False),
                    'last_crawled': item.get('last_crawled'),
                    'status': item.get('status', 'pending'),
                    'site_type': item.get('site_type'),
                    'last_error': item.get('last_error'),
                    'retry_count': item.get('retry_count', 0),
                    'priority_score': item.get('priority_score'),
                    'total_crawls': item.get('total_crawls', 0),
                    'success_crawls': item.get('success_crawls', 0),
                    'success_rate': item.get('success_rate'),
                    'total_anime_found': item.get('total_anime_found', 0),
                    'avg_quality_score': item.get('avg_quality_score'),
                    'health_score': item.get('health_score'),
                    'updated_at': datetime.now(),
                }
                self.domain_col.insert_one(doc)
                logger.info(f'[Pipeline] 新增域名: {domain}')

        except pymongo.errors.DuplicateKeyError:
            logger.debug(f'[Pipeline] 域名已存在: {domain}')
        except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure) as e:
            logger.error(f'[Pipeline] MongoDB 错误: {e}')
            raise

        return item

    def _ensure_indexes(self):
        """创建必要的索引"""
        try:
            self.anime_col.create_index('dedup_key', unique=True)
            self.anime_col.create_index('title')
            self.anime_col.create_index('year')
            self.anime_col.create_index('director')
            self.anime_col.create_index('genres')
            self.anime_col.create_index('source_domain')
            self.anime_col.create_index('quality_score')
            self.anime_col.create_index('normalized_title')
            self.anime_col.create_index('aliases')
            self.anime_col.create_index('play_sources.domain')
            self.anime_col.create_index('play_sources.provider_id')
            self.anime_col.create_index('play_sources.source_id')
            self.anime_col.create_index([('year', -1), ('discovered_at', -1)])
            self.anime_col.create_index('discovered_at')

            self.domain_col.create_index('domain', unique=True)
            self.domain_col.create_index('status')
            self.domain_col.create_index('is_anime_site')
            self.domain_col.create_index('priority_score')
            self.domain_col.create_index('health_score')
            self.domain_col.create_index([('is_anime_site', 1), ('status', 1)])

            logger.info('[Pipeline] MongoDB 索引创建完成')
        except Exception as e:
            logger.warning(f'[Pipeline] 创建索引时出错: {e}')

    def _calculate_quality_score(self, item):
        """根据字段完整度给结果打分。"""
        score = 0.0

        if item.get('title'):
            score += 0.2
        if item.get('year'):
            score += 0.1
        if item.get('director'):
            score += 0.1
        if item.get('synopsis'):
            score += 0.15
        if item.get('poster_url') or item.get('poster_local'):
            score += 0.15
        if item.get('genres'):
            score += 0.1
        if item.get('voice_actors'):
            score += 0.1

        play_sources = item.get('play_sources') or []
        if play_sources:
            score += 0.1
            episode_count = item.get('total_episode_count')
            if episode_count is None:
                episode_count = sum(len(source.get('episodes', [])) for source in play_sources)
            if episode_count >= 3:
                score += 0.1

        confidence = item.get('extractor_confidence')
        if confidence is not None:
            score = (score * 0.8) + (min(max(float(confidence), 0.0), 1.0) * 0.2)

        return round(min(score, 1.0), 3)

    def _update_domain_metrics(self, item, crawl_succeeded):
        source_domain = item.get('source_domain')
        if not source_domain:
            return

        domain_doc = self.domain_col.find_one({'domain': source_domain.lower()})
        if not domain_doc:
            return

        metrics = CrawlMetrics.build_domain_update(
            domain_doc,
            crawl_succeeded=crawl_succeeded,
            quality_score=item.get('quality_score'),
            anime_count_delta=1 if item.get('title') else 0,
        )
        self.domain_col.update_one(
            {'_id': domain_doc['_id']},
            {'$set': metrics},
        )
