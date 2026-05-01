"""URL 特征分析。"""

import re


class URLFeatureAnalyzer:
    """根据 URL 对页面类型和置信度做额外判断。"""

    DETAIL_PATTERNS = [
        r'/detail/\d+',
        r'/anime/\d+',
        r'/video/\d+',
        r'/vod/\d+',
        r'/play/\d+',
        r'/bangumi/\d+',
        r'/post/\d+',
        r'/archives/\d+',
        r'/article/.+\.html',
    ]

    LIST_PATTERNS = [
        r'/list',
        r'/catalog',
        r'/show',
        r'/type/',
        r'/分类/',
        r'/rank',
    ]

    def analyze(self, url):
        url = url or ''

        if any(re.search(pattern, url, re.IGNORECASE) for pattern in self.DETAIL_PATTERNS):
            return {
                'page_type': 'detail',
                'score': 0.25,
            }

        if any(re.search(pattern, url, re.IGNORECASE) for pattern in self.LIST_PATTERNS):
            return {
                'page_type': 'list',
                'score': 0.15,
            }

        return {
            'page_type': 'unknown',
            'score': 0.0,
        }
