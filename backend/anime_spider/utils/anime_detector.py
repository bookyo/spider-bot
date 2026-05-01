"""动画内容检测工具 - 判断页面是否为动画相关内容"""

import re
import json
import logging
from urllib.parse import urlparse
from config.keywords import (
    ANIME_CONTENT_KEYWORDS,
    ANIME_URL_PATTERNS,
)

logger = logging.getLogger(__name__)


class AnimeDetector:
    """动画内容检测器"""

    # 播放器特征
    PLAYER_INDICATORS = [
        'dplayer', 'artplayer', 'videojs', 'ckplayer',
        'jwplayer', 'flowplayer', 'html5player',
        'video-player', 'player-wrapper', 'play-wrap',
        '<video', 'm3u8', 'hls.js', 'flv.js',
    ]

    # 分集列表特征
    EPISODE_INDICATORS = [
        'episode', 'ep-list', 'episode-list', 'play-list',
        '选集', '分集', '剧集', '播放列表',
        '第.*集', '第.*话', 'EP\\d+',
    ]

    def detect(self, response):
        """检测页面是否为动画相关内容

        Args:
            response: Scrapy Response 对象

        Returns:
            dict: {
                'is_anime': bool,
                'confidence': float,  # 0-1 置信度
                'title': str,
                'detail_url': str,
            }
        """
        url = response.url
        content = response.text
        content_lower = content.lower()

        scores = {
            'url_pattern': 0,
            'keyword': 0,
            'player': 0,
            'episode': 0,
        }

        # 1. URL 模式匹配
        for pattern in ANIME_URL_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                scores['url_pattern'] += 0.3
                break

        # 2. 关键词匹配
        keyword_count = sum(1 for kw in ANIME_CONTENT_KEYWORDS if kw.lower() in content_lower)
        scores['keyword'] = min(keyword_count * 0.05, 0.3)

        # 3. 播放器特征
        player_count = sum(1 for indicator in self.PLAYER_INDICATORS if indicator.lower() in content_lower)
        scores['player'] = min(player_count * 0.1, 0.2)

        # 4. 分集列表特征
        episode_count = 0
        for indicator in self.EPISODE_INDICATORS:
            if re.search(indicator, content, re.IGNORECASE):
                episode_count += 1
        scores['episode'] = min(episode_count * 0.1, 0.2)

        # 计算总分
        total_score = sum(scores.values())
        is_anime = total_score >= 0.4
        confidence = min(total_score, 1.0)

        # 提取标题
        title = self._extract_title(response)

        logger.debug(
            f'[AnimeDetector] {url} - '
            f'is_anime={is_anime}, confidence={confidence:.2f}, '
            f'scores={scores}'
        )

        return {
            'is_anime': is_anime,
            'confidence': confidence,
            'title': title,
            'detail_url': url,
        }

    def _extract_title(self, response):
        """从页面提取标题"""
        # 优先从 og:title 提取
        og_title = response.css('meta[property="og:title"]::attr(content)').get()
        if og_title and len(og_title.strip()) > 1:
            title = og_title.strip()
            # 清理站点名称后缀 (如 " - AGE动漫", " - 樱花动漫")
            title = re.sub(r'\s*[-_|]\s*[^-_|]+$', '', title)
            if len(title) > 1:
                return title

        # 尝试多种方式提取标题
        selectors = [
            'h1::text',
            '.title::text',
            '.video-title::text',
            '.anime-title::text',
            '.name::text',
            'title::text',
        ]

        for selector in selectors:
            title = response.css(selector).get()
            if title:
                title = title.strip()
                # 清理标题中的多余信息
                title = re.sub(r'\s*[-_|].*$', '', title)
                if len(title) > 1 and len(title) < 200:
                    return title

        return None

    def _extract_director(self, response):
        """提取导演"""
        # 优先从 og:video:director 提取
        og_director = response.css('meta[property="og:video:director"]::attr(content)').get()
        if og_director and og_director.strip():
            return og_director.strip()

        # 从 JSON-LD 提取
        json_ld = response.css('script[type="application/ld+json"]::text').getall()
        for script in json_ld:
            try:
                data = json.loads(script)
                if isinstance(data, dict):
                    creators = data.get('creator', [])
                    if isinstance(creators, list) and creators:
                        c = creators[0]
                        if isinstance(c, dict) and c.get('@type') and '导演' not in str(c.get('@type', '')):
                            return str(c.get('@type', ''))
            except (json.JSONDecodeError, KeyError):
                pass

        # lmm85: .video-info-itemtitle 包含 "导演"，取同级 .video-info-item 中的 a span
        for sel in response.css('.video-info-items'):
            label = sel.css('.video-info-itemtitle::text').get() or ''
            if '导演' in label:
                actors = sel.css('.video-info-item a span::text').getall()
                if actors:
                    return '/'.join(a.strip() for a in actors if a.strip())

        # yhdm7: .module-info-item-title 包含 "导演"
        for sel in response.css('.module-info-item'):
            label = sel.css('.module-info-item-title::text').get() or ''
            if '导演' in label:
                actors = sel.css('.module-info-item-content a::text').getall()
                if actors and actors != ['未知']:
                    return '/'.join(a.strip() for a in actors if a.strip())

        return None

    def is_detail_page(self, response):
        """判断是否为动画详情页（而非列表页、首页等）"""
        url = response.url
        content = response.text.lower()

        # 详情页通常有更具体的 URL 模式
        detail_patterns = [
            r'/detail/\d+',
            r'/anime/\d+',
            r'/video/\d+',
            r'/vod/\d+',
            r'/play/\d+',
            r'/bangumi/\d+',
            r'/post/\d+',       # MacCMS / 樱花动漫等
            r'/article/.+\.html',  # yhdm7 等
            r'/archives/\d+',   # omofun / Z-Blog 等
        ]

        for pattern in detail_patterns:
            if re.search(pattern, url):
                return True

        # 检查 og:type 是否为视频类型（通用兼容）
        og_type = response.css('meta[property="og:type"]::attr(content)').get()
        if og_type and ('video' in og_type.lower() or 'movie' in og_type.lower()):
            return True

        # 详情页通常包含播放器和分集列表
        has_player = any(ind in content for ind in self.PLAYER_INDICATORS)
        has_episodes = any(re.search(ind, content, re.IGNORECASE) for ind in self.EPISODE_INDICATORS)

        return has_player and has_episodes

    def extract_metadata(self, response):
        """从详情页提取动画元数据"""
        content = response.text
        metadata = {
            'title': self._extract_title(response),
            'director': self._extract_director(response),
            'year': self._extract_year(response),
            'voice_actors': self._extract_voice_actors(response),
            'synopsis': self._extract_synopsis(response),
            'poster_url': self._extract_poster(response),
            'genres': self._extract_genres(response),
        }

        return metadata

    def _extract_field(self, response, selectors):
        """通用字段提取"""
        for selector in selectors:
            # CSS 选择器
            value = response.css(f'{selector}::text').get()
            if value:
                return value.strip()

            # 尝试 XPath
            value = response.xpath(f'//*[contains(text(), "{selector}")]/following-sibling::*//text()').get()
            if value:
                return value.strip()

        return None

    def _extract_year(self, response):
        """提取年份"""
        # lmm85: .video-info-aux 中的年份链接
        year_links = response.css('.video-info-aux .tag-link span::text').getall()
        for text in year_links:
            text = text.strip()
            if text.isdigit() and len(text) == 4:
                year = int(text)
                if 1900 <= year <= 2030:
                    return year

        # yhdm7: .module-info-tag 中的年份链接
        year_links = response.css('.module-info-tag .module-info-tag-link a::text').getall()
        for text in year_links:
            text = text.strip()
            if text.isdigit() and len(text) == 4:
                year = int(text)
                if 1900 <= year <= 2030:
                    return year

        # 通用: 从页面文本提取
        content = response.text
        year_patterns = [
            r'(?:年份|年|year)[：:\s]*(\d{4})',
            r'(\d{4})年',
            r'released[：:\s]*(\d{4})',
        ]

        for pattern in year_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                year = int(match.group(1))
                if 1900 <= year <= 2030:
                    return year

        return None

    def _extract_voice_actors(self, response):
        """提取声优/演员列表"""
        actors = []

        # 优先从 og:video:actor 提取
        og_actor = response.css('meta[property="og:video:actor"]::attr(content)').get()
        if og_actor and og_actor.strip():
            for sep in [',', '/', '、', '|']:
                if sep in og_actor:
                    actors = [a.strip() for a in og_actor.split(sep) if a.strip()]
                    break
            if not actors and og_actor.strip():
                actors = [og_actor.strip()]

        if actors:
            return actors[:20]

        # lmm85: .video-info-itemtitle 包含 "声优"/"主演"
        if not actors:
            for sel in response.css('.video-info-items'):
                label = sel.css('.video-info-itemtitle::text').get() or ''
                if '声优' in label or '主演' in label or '演员' in label:
                    found = sel.css('.video-info-item a span::text').getall()
                    if found:
                        actors = [a.strip() for a in found if a.strip()]
                        break

        # yhdm7: .module-info-item-title 包含 "导演"/"主演"
        if not actors:
            for sel in response.css('.module-info-item'):
                label = sel.css('.module-info-item-title::text').get() or ''
                if '声优' in label or '主演' in label or '演员' in label:
                    found = sel.css('.module-info-item-content a::text').getall()
                    if found and found != ['未知']:
                        actors = [a.strip() for a in found if a.strip()]
                        break

        # 通用 CSS 选择器
        if not actors:
            actor_selectors = [
                '.actors a::text', '.actor a::text',
                '.voice-actor a::text', '.cv a::text',
                '.info-actors a::text', '.cast a::text',
            ]
            for selector in actor_selectors:
                found = response.css(selector).getall()
                if found:
                    actors.extend([a.strip() for a in found if a.strip()])
                    break

        if actors:
            return list(set(actors))[:20]

        # 从文本中提取
        content = response.text
        actor_match = re.search(r'(?:声优|配音|演员|cast)[：:\s]*([^<\n]+)', content, re.IGNORECASE)
        if actor_match:
            actor_text = actor_match.group(1)
            for sep in [',', '/', '、', ' ', '|']:
                if sep in actor_text:
                    actors = [a.strip() for a in actor_text.split(sep) if a.strip()]
                    return actors[:20]

        return []

    def _extract_synopsis(self, response):
        """提取简介"""
        # 优先从 og:description 提取
        og_desc = response.css('meta[property="og:description"]::attr(content)').get()
        if og_desc and len(og_desc.strip()) > 10:
            return og_desc.strip()[:2000]

        # yhdm7: .module-info-introduction-content
        intro = response.css('.module-info-introduction-content p::text').get()
        if intro and len(intro.strip()) > 10:
            return intro.strip()[:2000]

        # lmm85: .video-info-items 中的简介
        desc_text = response.css('.video-info-items .video-info-item::text').getall()
        for text in desc_text:
            text = text.strip()
            if len(text) > 30 and '导演' not in text and '声优' not in text:
                return text[:2000]

        synopsis_selectors = [
            '.description::text', '.synopsis::text',
            '.intro::text', '.summary::text',
            '.plot::text', '.story::text',
            '.info-desc::text', '.detail-desc::text',
        ]

        for selector in synopsis_selectors:
            text = response.css(selector).get()
            if text and len(text.strip()) > 10:
                return text.strip()[:2000]

        # 尝试 XPath
        xpath_patterns = [
            '//*[contains(@class, "desc")]//text()',
            '//*[contains(@class, "intro")]//text()',
            '//*[contains(@class, "synopsis")]//text()',
        ]

        for xpath in xpath_patterns:
            texts = response.xpath(xpath).getall()
            if texts:
                full_text = ' '.join(t.strip() for t in texts if t.strip())
                if len(full_text) > 10:
                    return full_text[:2000]

        return None

    def _extract_poster(self, response):
        """提取海报图片"""
        poster_selectors = [
            'meta[property="og:image"]::attr(content)',
            '.stui-vodlist__thumb img::attr(data-original)',  # MacCMS 樱花动漫
            '.module-item-pic img::attr(src)',                 # lmm85
            '.module-item-pic img::attr(data-original)',
            '.video_detail_img img::attr(src)',               # agedm
            '.poster img::attr(src)',
            '.cover img::attr(src)',
            '.thumb img::attr(src)',
            '.video-cover img::attr(src)',
            '.anime-cover img::attr(src)',
        ]

        for selector in poster_selectors:
            url = response.css(selector).get()
            if url and not url.endswith('load.gif'):  # 跳过懒加载占位图
                return response.urljoin(url)

        return None

    def _extract_genres(self, response):
        """提取类型标签"""
        genres = []

        # 优先从 og:video:class 提取
        og_class = response.css('meta[property="og:video:class"]::attr(content)').get()
        if og_class and og_class.strip():
            genres.append(og_class.strip())

        # lmm85: .video-info-aux 中的分类链接（排除年份和地区）
        aux_links = response.css('.video-info-aux .tag-link')
        for link in aux_links:
            href = link.css('::attr(href)').get() or ''
            text = link.css('span::text').get() or ''
            if '/type/' in href or '/class/' in href:
                if text.strip() and not text.strip().isdigit():
                    genres.append(text.strip())

        # yhdm7: .module-info-tag 中的类型链接（排除年份和地区）
        tag_links = response.css('.module-info-tag .module-info-tag-link a::text').getall()
        for text in tag_links:
            text = text.strip()
            if text and not text.isdigit() and len(text) < 20:
                if text not in ('未知',):
                    genres.append(text)

        # 通用 CSS 选择器
        if not genres:
            genre_selectors = [
                '.genre a::text', '.tag a::text',
                '.type a::text', '.category a::text',
                '.genres a::text', '.tags a::text',
            ]
            for selector in genre_selectors:
                found = response.css(selector).getall()
                if found:
                    genres.extend([g.strip() for g in found if g.strip()])

        return list(set(genres))[:10] if genres else []
