"""域名调度优先级计算。"""

from datetime import datetime, timezone


class DomainPriorityScorer:
    """根据站点状态和历史表现给域名排序。"""

    def score(self, domain_doc):
        domain_doc = domain_doc or {}
        score = 0.0

        if domain_doc.get('is_anime_site'):
            score += 0.3

        status = domain_doc.get('status')
        if status == 'pending':
            score += 0.25
        elif status == 'failed':
            score += 0.05
        elif status == 'completed':
            score += 0.1

        retry_count = domain_doc.get('retry_count') or 0
        score -= min(retry_count * 0.05, 0.25)

        success_rate = domain_doc.get('success_rate')
        if success_rate is not None:
            score += min(max(float(success_rate), 0.0), 1.0) * 0.2

        quality_score = domain_doc.get('avg_quality_score')
        if quality_score is not None:
            score += min(max(float(quality_score), 0.0), 1.0) * 0.15

        last_crawled = domain_doc.get('last_crawled')
        if last_crawled:
            score += self._staleness_bonus(last_crawled)
        else:
            score += 0.1

        return round(max(score, 0.0), 4)

    def _staleness_bonus(self, last_crawled):
        if isinstance(last_crawled, str):
            try:
                last_crawled = datetime.fromisoformat(last_crawled)
            except ValueError:
                return 0.0

        if last_crawled.tzinfo is None:
            last_crawled = last_crawled.replace(tzinfo=timezone.utc)

        delta = datetime.now(timezone.utc) - last_crawled
        days = max(delta.total_seconds() / 86400, 0)
        return min(days / 30, 0.2)
