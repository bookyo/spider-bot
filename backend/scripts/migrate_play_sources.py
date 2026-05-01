#!/usr/bin/env python3
"""清洗旧播放源结构并补全 provider_id/source_id。"""

import os
import sys

from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from anime_spider.utils.dedup import (
    normalize_play_sources_for_storage,
    summarize_play_sources,
)


def main():
    client = MongoClient('mongodb://localhost:27017')
    db = client['anime_db']
    anime_col = db['anime']

    migrated = 0
    for doc in anime_col.find({}):
        play_sources = doc.get('play_sources', [])
        if not play_sources:
            continue

        cleaned_sources = []
        source_urls = doc.get('source_urls') or []
        anime_key = None
        for value in source_urls:
            if '/post/' in str(value) or '/play/' in str(value):
                import re
                match = re.search(r'/(?:post|play)/(\d+)', str(value))
                if match:
                    anime_key = match.group(1)
                    break
        for index, source in enumerate(play_sources):
            source = dict(source)
            source_name = source.get('source_name')
            if not source_name:
                source['source_name'] = f'legacy-{index + 1}'
            cleaned_sources.append(source)

        merged_sources = normalize_play_sources_for_storage(cleaned_sources, anime_key=anime_key)
        summary = summarize_play_sources(merged_sources)

        anime_col.update_one(
            {'_id': doc['_id']},
            {'$set': {
                'play_sources': merged_sources,
                'latest_episode': summary['latest_episode'],
                'total_episode_count': summary['total_episode_count'],
                'new_episode_count': 0,
                'incremental_found': False,
            }},
        )
        migrated += 1

    print(f'migrated={migrated}')
    client.close()


if __name__ == '__main__':
    main()
