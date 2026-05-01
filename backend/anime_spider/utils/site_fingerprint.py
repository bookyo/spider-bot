"""站型指纹识别。"""


class SiteFingerprint:
    """根据页面结构识别常见站型。"""

    SIGNATURES = {
        'maccms': [
            'stui-vodlist',
            'stui-content__playlist',
            'mac_url',
            'vod-detail',
        ],
        'module-theme': [
            'module-item',
            'module-info',
            'module-play-list',
            'module-info-tag',
        ],
        'video-info-theme': [
            'video-info-items',
            'video-info-aux',
            'scroll-content',
        ],
    }

    def detect(self, response):
        content = response.text.lower()
        scores = {}

        for site_type, indicators in self.SIGNATURES.items():
            score = sum(1 for indicator in indicators if indicator.lower() in content)
            if score:
                scores[site_type] = score

        if not scores:
            return {
                'site_type': 'generic',
                'confidence': 0.0,
                'scores': {},
            }

        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        confidence = min(best_score / max(len(self.SIGNATURES[best_type]), 1), 1.0)

        return {
            'site_type': best_type,
            'confidence': round(confidence, 2),
            'scores': scores,
        }
