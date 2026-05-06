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
            return self._clean_person_text(og_director.strip())

        # 从 JSON-LD 提取
        json_ld = response.css('script[type="application/ld+json"]::text').getall()
        for script in json_ld:
            try:
                data = json.loads(script)
                payloads = data if isinstance(data, list) else [data]
                for payload in payloads:
                    if not isinstance(payload, dict):
                        continue
                    for key in ['director', 'creator']:
                        names = self._extract_people_from_json_ld(payload.get(key))
                        if names:
                            return '/'.join(names[:10])
            except (json.JSONDecodeError, KeyError):
                pass

        # lmm85: .video-info-itemtitle 包含 "导演"，取同级 .video-info-item 中的 a span
        for sel in response.css('.video-info-items'):
                label = sel.css('.video-info-itemtitle::text').get() or ''
                if '导演' in label:
                    actors = sel.css('.video-info-item a span::text').getall()
                    if actors:
                        return '/'.join(self._dedupe_people(actors))

        # yhdm7: .module-info-item-title 包含 "导演"
        for sel in response.css('.module-info-item'):
                label = sel.css('.module-info-item-title::text').get() or ''
                if '导演' in label:
                    actors = sel.css('.module-info-item-content a::text').getall()
                    if actors and actors != ['未知']:
                        return '/'.join(self._dedupe_people(actors))

        fallback = self._extract_labeled_text(
            response,
            labels=['导演', '导演：', '导演:'],
        )
        if fallback:
            people = self._split_people_text(fallback)
            if people:
                return '/'.join(people[:10])

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
            'douban_rating': self._extract_douban_rating(response),
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
        # 优先从 JSON-LD 提取
        json_ld = response.css('script[type="application/ld+json"]::text').getall()
        for script in json_ld:
            try:
                data = json.loads(script)
                payloads = data if isinstance(data, list) else [data]
                for payload in payloads:
                    if not isinstance(payload, dict):
                        continue
                    for key in ['datePublished', 'dateCreated', 'uploadDate']:
                        year = self._parse_year_value(payload.get(key))
                        if year is not None:
                            return year
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        # lmm85: .video-info-aux 中的年份链接
        year_links = response.css('.video-info-aux .tag-link span::text').getall()
        for text in year_links:
            year = self._parse_year_value(text)
            if year is not None:
                return year

        # yhdm7: .module-info-tag 中的年份链接
        year_links = response.css('.module-info-tag .module-info-tag-link a::text').getall()
        for text in year_links:
            year = self._parse_year_value(text)
            if year is not None:
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
                year = self._parse_year_value(match.group(1))
                if year is not None:
                    return year

        return None

    def _extract_voice_actors(self, response):
        """提取声优/演员列表"""
        actors = []

        # 优先从 og:video:actor 提取
        og_actor = response.css('meta[property="og:video:actor"]::attr(content)').get()
        if og_actor and og_actor.strip():
            actors = self._split_people_text(og_actor)

        if actors:
            return actors[:20]

        json_ld = response.css('script[type="application/ld+json"]::text').getall()
        for script in json_ld:
            try:
                data = json.loads(script)
                payloads = data if isinstance(data, list) else [data]
                for payload in payloads:
                    if not isinstance(payload, dict):
                        continue
                    for key in ['actor', 'actors', 'performer']:
                        names = self._extract_people_from_json_ld(payload.get(key))
                        if names:
                            return names[:20]
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        # lmm85: .video-info-itemtitle 包含 "声优"/"主演"
        if not actors:
            for sel in response.css('.video-info-items'):
                label = sel.css('.video-info-itemtitle::text').get() or ''
                if '声优' in label or '主演' in label or '演员' in label:
                    found = sel.css('.video-info-item a span::text').getall()
                    if found:
                        actors = self._dedupe_people(found)
                        break

        # yhdm7: .module-info-item-title 包含 "导演"/"主演"
        if not actors:
            for sel in response.css('.module-info-item'):
                label = sel.css('.module-info-item-title::text').get() or ''
                if '声优' in label or '主演' in label or '演员' in label:
                    found = sel.css('.module-info-item-content a::text').getall()
                    if found and found != ['未知']:
                        actors = self._dedupe_people(found)
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
                    actors.extend(self._dedupe_people(found))
                    break

        if actors:
            return self._dedupe_people(actors)[:20]

        # 从文本中提取
        fallback = self._extract_labeled_text(
            response,
            labels=['声优', '配音', '演员', '主演', 'cast', 'Cast'],
        )
        if fallback:
            actors = self._split_people_text(fallback)
            if actors:
                return actors[:20]

        return []

    def _extract_synopsis(self, response):
        """提取简介"""
        # 豆瓣 subject 页: span[property="v:summary"] 内用 <br> 分段。
        douban_summary = self._extract_douban_summary(response)
        if douban_summary:
            return douban_summary[:2000]

        # 优先从 og:description 提取
        og_desc = response.css('meta[property="og:description"]::attr(content)').get()
        if og_desc and len(og_desc.strip()) > 10:
            cleaned = self._clean_synopsis_text(og_desc)
            if cleaned:
                return cleaned[:2000]

        # JSON-LD 描述
        json_ld = response.css('script[type="application/ld+json"]::text').getall()
        for script in json_ld:
            try:
                data = json.loads(script)
                payloads = data if isinstance(data, list) else [data]
                for payload in payloads:
                    if not isinstance(payload, dict):
                        continue
                    description = payload.get('description')
                    cleaned = self._clean_synopsis_text(description)
                    if cleaned:
                        return cleaned[:2000]
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        # yhdm7: .module-info-introduction-content
        intro = response.css('.module-info-introduction-content p::text').get()
        if intro and len(intro.strip()) > 10:
            cleaned = self._clean_synopsis_text(intro)
            if cleaned:
                return cleaned[:2000]

        # lmm85: .video-info-items 中的简介
        desc_text = response.css('.video-info-items .video-info-item::text').getall()
        for text in desc_text:
            cleaned = self._clean_synopsis_text(text)
            if cleaned and len(cleaned) > 30 and '导演' not in cleaned and '声优' not in cleaned:
                return cleaned[:2000]

        synopsis_selectors = [
            '.description::text', '.synopsis::text',
            '.intro::text', '.summary::text',
            '.plot::text', '.story::text',
            '.info-desc::text', '.detail-desc::text',
        ]

        for selector in synopsis_selectors:
            text = response.css(selector).get()
            cleaned = self._clean_synopsis_text(text)
            if cleaned and len(cleaned) > 10:
                return cleaned[:2000]

        # 尝试 XPath
        xpath_patterns = [
            '//*[contains(@class, "desc")]//text()',
            '//*[contains(@class, "intro")]//text()',
            '//*[contains(@class, "synopsis")]//text()',
        ]

        for xpath in xpath_patterns:
            texts = response.xpath(xpath).getall()
            if texts:
                full_text = self._clean_synopsis_text(' '.join(t.strip() for t in texts if t.strip()))
                if full_text and len(full_text) > 10:
                    return full_text[:2000]

        return None

    def _extract_douban_summary(self, response):
        summary_nodes = response.xpath('//span[@property="v:summary"]')
        if not summary_nodes:
            return None

        chunks = []
        for node in summary_nodes:
            texts = node.xpath('.//text()').getall()
            if not texts:
                continue
            lines = []
            for text in texts:
                cleaned = self._collapse_space(text)
                if cleaned:
                    lines.append(cleaned)
            if lines:
                chunks.append('\n'.join(lines))

        cleaned = self._clean_synopsis_text('\n'.join(chunks))
        return cleaned

    def _extract_people_from_json_ld(self, value):
        if not value:
            return []
        values = value if isinstance(value, list) else [value]
        names = []
        for item in values:
            if isinstance(item, str):
                names.extend(self._split_people_text(item))
            elif isinstance(item, dict):
                name = item.get('name') or item.get('@name')
                if name:
                    names.extend(self._split_people_text(str(name)))
        return self._dedupe_people(names)

    def _parse_year_value(self, value):
        if value is None:
            return None
        text = str(value).strip()
        match = re.search(r'(19\d{2}|20\d{2}|2030)', text)
        if not match:
            return None
        year = int(match.group(1))
        if 1900 <= year <= 2030:
            return year
        return None

    def _extract_labeled_text(self, response, labels):
        texts = response.css('body *::text').getall()
        cleaned_texts = [self._collapse_space(text) for text in texts if self._collapse_space(text)]
        for index, text in enumerate(cleaned_texts):
            for label in labels:
                if text == label or text.startswith(f'{label}:') or text.startswith(f'{label}：'):
                    suffix = re.sub(rf'^{re.escape(label)}[：:\s]*', '', text, flags=re.IGNORECASE).strip()
                    if suffix:
                        return suffix
                    if index + 1 < len(cleaned_texts):
                        return cleaned_texts[index + 1]
        body_text = self._collapse_space(' '.join(cleaned_texts))
        for label in labels:
            match = re.search(rf'{re.escape(label)}[：:\s]+(.{{1,120}}?)(?:\s{{2,}}|导演|年份|类型|地区|$)', body_text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _split_people_text(self, text):
        cleaned = self._clean_person_text(text)
        if not cleaned:
            return []
        values = re.split(r'[,，/|、]+', cleaned)
        return self._dedupe_people(values)

    def _dedupe_people(self, values):
        items = []
        seen = set()
        for raw in values:
            cleaned = self._clean_person_text(raw)
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            items.append(cleaned)
        return items

    def _clean_person_text(self, text):
        value = self._collapse_space(text)
        value = re.sub(r'^(?:导演|主演|演员|声优|配音|cast)[：:\s]*', '', value, flags=re.IGNORECASE)
        value = re.sub(r'^(?:未知|暂无|--|-|n/?a)$', '', value, flags=re.IGNORECASE)
        return value.strip(' /|,，、')

    def _clean_synopsis_text(self, text):
        if text is None:
            return None
        lines = [self._collapse_space(line) for line in str(text).splitlines()]
        value = '\n'.join(line for line in lines if line)
        value = re.sub(r'^(?:简介|剧情简介|内容简介|剧情|介绍)[：:\s]*', '', value)
        value = value.strip()
        if len(value) <= 10:
            return None
        return value

    def _collapse_space(self, text):
        if text is None:
            return ''
        return re.sub(r'\s+', ' ', str(text)).strip()

    def _extract_poster(self, response):
        """提取海报图片"""
        douban_poster = self._extract_douban_poster(response)
        if douban_poster:
            return douban_poster

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
                return self._normalize_poster_url(response.urljoin(url))

        return None

    def _extract_douban_poster(self, response):
        if 'douban.com' not in response.url:
            return None

        json_ld = response.css('script[type="application/ld+json"]::text').getall()
        for script in json_ld:
            try:
                data = json.loads(script)
                payloads = data if isinstance(data, list) else [data]
                for payload in payloads:
                    if not isinstance(payload, dict):
                        continue
                    image = payload.get('image')
                    if isinstance(image, list):
                        image = image[0] if image else None
                    if isinstance(image, dict):
                        image = image.get('url') or image.get('@id')
                    if image:
                        return self._normalize_douban_poster_url(response.urljoin(str(image)))
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        og_image = response.css('meta[property="og:image"]::attr(content)').get()
        if og_image:
            return self._normalize_douban_poster_url(response.urljoin(og_image))

        return None

    def _normalize_poster_url(self, url):
        if not url:
            return None
        if 'doubanio.com' in url or 'douban.com' in url:
            return self._normalize_douban_poster_url(url)
        return url

    def _normalize_douban_poster_url(self, url):
        if not url:
            return None
        return str(url).replace('s_ratio_poster', 'm')

    def _extract_douban_rating(self, response):
        if 'douban.com' not in response.url:
            return None

        json_ld = response.css('script[type="application/ld+json"]::text').getall()
        for script in json_ld:
            try:
                data = json.loads(script)
                payloads = data if isinstance(data, list) else [data]
                for payload in payloads:
                    if not isinstance(payload, dict):
                        continue
                    rating = payload.get('aggregateRating')
                    if isinstance(rating, dict):
                        value = self._parse_rating_value(rating.get('ratingValue'))
                        if value is not None:
                            return value
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        for selector in [
            'strong.rating_num::text',
            'strong[property="v:average"]::text',
            '[property="v:average"]::text',
        ]:
            value = self._parse_rating_value(response.css(selector).get())
            if value is not None:
                return value

        return None

    def _parse_rating_value(self, value):
        if value is None:
            return None
        try:
            rating = float(str(value).strip())
        except (TypeError, ValueError):
            return None
        if 0 <= rating <= 10:
            return rating
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
