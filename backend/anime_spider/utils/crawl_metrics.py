"""抓取统计与健康度计算。"""


class CrawlMetrics:
    """汇总域名和内容质量指标。"""

    @staticmethod
    def build_domain_update(existing, *, crawl_succeeded=None, quality_score=None, anime_count_delta=0):
        existing = existing or {}

        total_crawls = int(existing.get('total_crawls') or 0)
        success_crawls = int(existing.get('success_crawls') or 0)
        total_anime = int(existing.get('total_anime_found') or 0)
        avg_quality = existing.get('avg_quality_score')

        if crawl_succeeded is not None:
            total_crawls += 1
            if crawl_succeeded:
                success_crawls += 1

        total_anime += anime_count_delta

        if quality_score is not None:
            if avg_quality is None:
                avg_quality = float(quality_score)
            else:
                sample_size = max(success_crawls, 1)
                avg_quality = ((float(avg_quality) * (sample_size - 1)) + float(quality_score)) / sample_size

        success_rate = (success_crawls / total_crawls) if total_crawls > 0 else None
        health_score = CrawlMetrics._health_score(success_rate, avg_quality, total_anime)

        return {
            'total_crawls': total_crawls,
            'success_crawls': success_crawls,
            'success_rate': round(success_rate, 4) if success_rate is not None else None,
            'total_anime_found': total_anime,
            'avg_quality_score': round(avg_quality, 4) if avg_quality is not None else None,
            'health_score': health_score,
        }

    @staticmethod
    def _health_score(success_rate, avg_quality, total_anime):
        score = 0.0
        if success_rate is not None:
            score += min(max(success_rate, 0.0), 1.0) * 0.45
        if avg_quality is not None:
            score += min(max(avg_quality, 0.0), 1.0) * 0.35
        if total_anime:
            score += min(total_anime / 200, 0.2)
        return round(min(score, 1.0), 4)
