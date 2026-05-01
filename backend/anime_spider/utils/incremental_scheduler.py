"""动画增量巡检调度。"""

from datetime import datetime, timedelta, timezone


class IncrementalScheduler:
    """根据最近更新时间和分集状态排序增量巡检候选。"""

    def score(self, anime_doc):
        anime_doc = anime_doc or {}
        score = 0.0

        total_episode_count = anime_doc.get('total_episode_count') or 0
        if total_episode_count > 0:
            score += min(total_episode_count / 100, 0.2)

        quality_score = anime_doc.get('quality_score')
        if quality_score is not None:
            score += min(max(float(quality_score), 0.0), 1.0) * 0.2

        if anime_doc.get('incremental_found'):
            score += 0.25

        last_incremental_check = anime_doc.get('last_incremental_check')
        score += self._staleness_bonus(last_incremental_check)

        latest_episode = anime_doc.get('latest_episode')
        if latest_episode:
            score += 0.1

        return round(min(score, 1.0), 4)

    def should_check(self, anime_doc, min_hours=6):
        last_incremental_check = anime_doc.get('last_incremental_check')
        if not last_incremental_check:
            return True

        if isinstance(last_incremental_check, str):
            try:
                last_incremental_check = datetime.fromisoformat(last_incremental_check)
            except ValueError:
                return True

        if last_incremental_check.tzinfo is None:
            last_incremental_check = last_incremental_check.replace(tzinfo=timezone.utc)

        return datetime.now(timezone.utc) - last_incremental_check >= timedelta(hours=min_hours)

    def build_targets(self, anime_doc):
        """构建轻量增量巡检目标，优先使用播放源 raw_url。"""
        anime_doc = anime_doc or {}
        targets = []
        seen = set()

        for source in anime_doc.get('play_sources') or []:
            raw_url = source.get('raw_url')
            if raw_url and raw_url not in seen:
                seen.add(raw_url)
                targets.append({
                    'url': raw_url,
                    'kind': 'play_source',
                    'domain': source.get('domain'),
                    'latest_episode': source.get('latest_episode'),
                    'episode_count': source.get('episode_count'),
                })

        for source_url in anime_doc.get('source_urls') or []:
            if source_url and source_url not in seen:
                seen.add(source_url)
                targets.append({
                    'url': source_url,
                    'kind': 'detail',
                    'domain': anime_doc.get('source_domain'),
                    'latest_episode': anime_doc.get('latest_episode'),
                    'episode_count': anime_doc.get('total_episode_count'),
                })

        return targets

    def _staleness_bonus(self, last_incremental_check):
        if not last_incremental_check:
            return 0.3

        if isinstance(last_incremental_check, str):
            try:
                last_incremental_check = datetime.fromisoformat(last_incremental_check)
            except ValueError:
                return 0.2

        if last_incremental_check.tzinfo is None:
            last_incremental_check = last_incremental_check.replace(tzinfo=timezone.utc)

        delta = datetime.now(timezone.utc) - last_incremental_check
        hours = max(delta.total_seconds() / 3600, 0)
        return min(hours / 72, 0.25)
