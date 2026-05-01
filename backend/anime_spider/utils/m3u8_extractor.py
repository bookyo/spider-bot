"""m3u8 链接提取工具 - 从页面中提取视频播放源"""

import json
import logging
import re
from urllib.parse import urlparse, urljoin

import requests

logger = logging.getLogger(__name__)


class M3U8Extractor:
    """m3u8 链接提取器"""

    # m3u8 链接正则模式
    M3U8_PATTERNS = [
        # 直接的 m3u8 链接
        r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*',
        # JavaScript 中的 m3u8 链接
        r'(?:source|url|file|src|video_url|play_url)\s*[:=]\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
        # JSON 格式中的 m3u8 链接
        r'"(?:url|src|file|link|playurl|play_url|video_url)"\s*:\s*"([^"]+\.m3u8[^"]*)"',
        # 单引号包裹的 m3u8 链接
        r"'([^']+\.m3u8[^']*)'",
        # 反引号包裹的 m3u8 链接
        r'`([^`]+\.m3u8[^`]*)`',
    ]

    # 常见的视频 API 路径
    VIDEO_API_PATTERNS = [
        r'/api/video/[^\s"\'<>]+',
        r'/api/play/[^\s"\'<>]+',
        r'/api/m3u8/[^\s"\'<>]+',
        r'/api/resource/[^\s"\'<>]+',
    ]

    # iframe 中的播放器域名特征
    PLAYER_DOMAINS = [
        'player', 'video', 'embed', 'iframe',
        'cdn', 'stream', 'play', 'media',
    ]

    SOURCE_NAME_SELECTORS = [
        '.nav-tabs li::text',
        '.tab-item::text',
        '.play-source-tab::text',
        '.module-tab-item span::text',
        '.stui-vodlist__head li::text',
        '.stui-pannel__head h2.title::text',
    ]

    PLAYABLE_EXTENSIONS = ('.m3u8', '.mp4', '.m4v', '.flv', '.mpd')

    def extract_ikanbot_play_sources(self, response, timeout=15):
        """针对 v.ikanbot.com 播放页，通过专用接口提取真实 m3u8 线路。"""
        domain = urlparse(response.url).netloc.lower()
        if domain != 'v.ikanbot.com':
            return []

        video_id = response.css('#current_id::attr(value)').get()
        e_token = response.css('#e_token::attr(value)').get()
        mtype = response.css('#mtype::attr(value)').get() or '2'
        if not video_id or not e_token:
            return []

        token = self._build_ikanbot_token(video_id, e_token)
        if not token:
            return []

        api_url = response.urljoin('/api/getResN')
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Referer': response.url,
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
        }
        params = {
            'videoId': video_id,
            'mtype': mtype,
            'token': token,
        }

        try:
            api_resp = requests.get(api_url, params=params, headers=headers, timeout=timeout)
            payload = api_resp.json()
        except Exception as exc:
            logger.debug('[M3U8Extractor] ikanbot 接口请求失败: %s', exc)
            return []

        if payload.get('state') != 1:
            logger.debug('[M3U8Extractor] ikanbot 接口未授权/无数据: %s', payload)
            return []

        data_list = ((payload.get('data') or {}).get('list') or [])
        play_sources = []
        for index, item in enumerate(data_list, start=1):
            source_name = f'线路{index}'
            try:
                groups = self._parse_ikanbot_res_data(item.get('resData'))
            except Exception as exc:
                logger.debug('[M3U8Extractor] ikanbot resData 解析失败: %s', exc)
                continue

            episodes = []
            for group in groups:
                new_name = group.get('newName')
                line_data = group.get('url') or ''
                for chunk in str(line_data).split('#'):
                    if '$' not in chunk:
                        continue
                    url_name, media_url = chunk.split('$', 1)
                    media_url = str(media_url).strip()
                    if not self._is_playable_media_url(media_url):
                        continue

                    episode = self._guess_episode_from_ikanbot_name(url_name, new_name)
                    episodes.append({
                        'episode': episode,
                        'url': media_url,
                    })

            if episodes:
                play_sources.append({
                    'source_name': source_name,
                    'domain': domain,
                    'episodes': episodes,
                    'quality': None,
                    'raw_url': response.url,
                })

        return self._dedupe_play_sources(play_sources)

    def _build_ikanbot_token(self, video_id, e_token):
        suffix = str(video_id)[-4:]
        if len(suffix) != 4 or not suffix.isdigit():
            return None

        token = str(e_token)
        segments = []
        for ch in suffix:
            index = int(ch) % 3 + 1
            segments.append(token[index:index + 8])
            token = token[index + 8:]
        return ''.join(segments)

    def _parse_ikanbot_res_data(self, raw_value):
        if raw_value is None:
            return []
        if isinstance(raw_value, list):
            return raw_value

        text = str(raw_value).strip()
        if not text:
            return []
        return json.loads(text)

    def _guess_episode_from_ikanbot_name(self, url_name, fallback_name=None):
        for candidate in [url_name, fallback_name]:
            if not candidate:
                continue
            match = re.search(r'(\d+)', str(candidate))
            if match:
                value = match.group(1)
                return value.zfill(2) if value.isdigit() else value
        return None

    def extract(self, response):
        """从页面中提取所有 m3u8 链接

        Args:
            response: Scrapy Response 对象

        Returns:
            list: [{'url': str, 'source': str, 'episode': str}]
        """
        results = []
        seen_urls = set()

        # 1. 从页面 HTML 直接提取
        direct_links = self._extract_from_html(response)
        for link in direct_links:
            if link['url'] not in seen_urls:
                seen_urls.add(link['url'])
                results.append(link)

        # 2. 从 JavaScript 代码提取
        js_links = self._extract_from_scripts(response)
        for link in js_links:
            if link['url'] not in seen_urls:
                seen_urls.add(link['url'])
                results.append(link)

        # 3. 从 iframe 嵌入页面提取
        iframe_links = self._extract_from_iframes(response)
        for link in iframe_links:
            if link['url'] not in seen_urls:
                seen_urls.add(link['url'])
                results.append(link)

        logger.debug(f'[M3U8Extractor] {response.url} 提取到 {len(results)} 个 m3u8 链接')
        return results

    def _extract_from_html(self, response):
        """从 HTML 中提取 m3u8 链接"""
        results = []
        content = response.text

        # 使用正则提取
        for pattern in self.M3U8_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                url = match if isinstance(match, str) else match[0] if match else ''
                url = url.strip()
                if url and '.m3u8' in url:
                    # 确保是完整 URL
                    if not url.startswith('http'):
                        url = urljoin(response.url, url)
                    results.append({
                        'url': url,
                        'source': 'html',
                        'episode': self._guess_episode(url, content),
                    })

        return results

    def _extract_from_scripts(self, response):
        """从 JavaScript 代码中提取 m3u8 链接"""
        results = []

        # 获取所有 script 标签内容
        scripts = response.css('script::text').getall()

        for script in scripts:
            # 提取 m3u8 链接
            for pattern in self.M3U8_PATTERNS:
                matches = re.findall(pattern, script, re.IGNORECASE)
                for match in matches:
                    url = match if isinstance(match, str) else match[0] if match else ''
                    url = url.strip()
                    if url and '.m3u8' in url:
                        if not url.startswith('http'):
                            url = urljoin(response.url, url)
                        results.append({
                            'url': url,
                            'source': 'javascript',
                            'episode': self._guess_episode(url, script),
                        })

            # 尝试解析 JSON 配置
            json_links = self._extract_from_json(script)
            results.extend(json_links)

        return results

    def _extract_from_json(self, script):
        """从 JSON 配置中提取 m3u8 链接"""
        results = []

        # 查找 JSON 对象
        json_pattern = r'\{[^{}]*"url"\s*:\s*"[^"]*\.m3u8[^"]*"[^{}]*\}'
        matches = re.findall(json_pattern, script)

        for match in matches:
            url_match = re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', match)
            if url_match:
                url = url_match.group(1)
                if not url.startswith('http'):
                    continue
                results.append({
                    'url': url,
                    'source': 'json_config',
                    'episode': self._guess_episode_from_json(match),
                })

        return results

    def _extract_from_iframes(self, response):
        """从 iframe 嵌入页面提取 m3u8 链接"""
        results = []

        # 获取所有 iframe 的 src
        iframe_srcs = response.css('iframe::attr(src)').getall()

        for src in iframe_srcs:
            if not src:
                continue

            # 构建完整 URL
            iframe_url = urljoin(response.url, src)

            # 检查是否可能是播放器 iframe
            parsed = urlparse(iframe_url)
            is_player = any(domain in parsed.netloc.lower() for domain in self.PLAYER_DOMAINS)

            if is_player or 'player' in iframe_url.lower() or 'embed' in iframe_url.lower():
                results.append({
                    'url': iframe_url,
                    'source': 'iframe',
                    'episode': None,
                    'needs_follow': True,  # 标记需要进一步请求
                })

        return results

    def _guess_episode(self, url, context=''):
        """猜测分集信息"""
        # 从 URL 中提取
        ep_patterns = [
            r'ep(\d+)',
            r'episode[_-]?(\d+)',
            r'第(\d+)[集话]',
            r'EP(\d+)',
            r'/(\d+)\.m3u8',
        ]

        for pattern in ep_patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return match.group(1).zfill(2)

        # 从上下文中提取
        if context:
            for pattern in ep_patterns:
                match = re.search(pattern, context, re.IGNORECASE)
                if match:
                    return match.group(1).zfill(2)

        return None

    def _guess_episode_from_json(self, json_str):
        """从 JSON 字符串中猜测分集"""
        # 尝试提取 episode 字段
        ep_match = re.search(r'"episode"\s*:\s*"?(\d+)"?', json_str)
        if ep_match:
            return ep_match.group(1).zfill(2)

        # 尝试提取 name 字段中的集数
        name_match = re.search(r'"name"\s*:\s*"([^"]*第(\d+)[集话][^"]*)"', json_str)
        if name_match:
            return name_match.group(2).zfill(2)

        return None

    def extract_episodes_from_page(self, response):
        """从页面中提取分集列表和对应的播放链接

        Returns:
            list: [{'episode': str, 'url': str}]
        """
        episodes = []

        # 常见的分集列表选择器
        episode_selectors = [
            '.stui-content__playlist a',        # MacCMS / 樱花动漫
            '.scroll-content a',                # lmm85
            'a.module-play-list-link',          # yhdm7
            'ul.video_detail_episode a',        # agedm
            '.episode-list a', '.ep-list a',
            '.play-list a', '.source-list a',
            '.chapter-list a', '.playlist a',
            '[data-episode]', '[data-ep]',
        ]

        for selector in episode_selectors:
            items = response.css(selector)
            if items:
                for item in items:
                    ep_num = (
                        item.css('::attr(data-episode)').get() or
                        item.css('::attr(data-ep)').get() or
                        item.css('::text').get()
                    )
                    ep_url = item.css('::attr(href)').get()

                    if ep_num:
                        # 清理分集号
                        ep_num = re.sub(r'[^\d]', '', ep_num)
                        if ep_num:
                            ep_num = ep_num.zfill(2)
                        else:
                            ep_num = None

                    if ep_url:
                        ep_url = response.urljoin(ep_url)

                    if ep_url:
                        episodes.append({
                            'episode': ep_num,
                            'url': ep_url,
                        })

                if episodes:
                    break

        return episodes

    def extract_play_page_entries(self, response):
        """从详情页提取分线路的播放页入口，不直接当作播放源落库。"""
        selector_groups = [
            ('.stui-pannel-box.b.playlist, .stui-pannel-box.playlist, .module-play-list, .module-play-list-content, .module-list', '.stui-content__playlist a, a.module-play-list-link, a'),
            ('.stui-content__playlist, .play-list, .playlist, .source-list', 'a'),
        ]

        source_names = self._extract_source_names(response)
        anime_key = self._extract_anime_play_key(response.url)
        groups_data = []

        for group_selector, item_selector in selector_groups:
            groups = response.css(group_selector)
            if not groups:
                continue

            for index, group in enumerate(groups):
                entries = []
                items = group.css(item_selector)
                for item in items:
                    ep_num = (
                        item.css('::attr(data-episode)').get() or
                        item.css('::attr(data-ep)').get() or
                        item.css('::text').get()
                    )
                    play_page_url = item.css('::attr(href)').get()
                    if ep_num:
                        ep_num = re.sub(r'[^\d.]', '', ep_num) or None
                        if ep_num and ep_num.isdigit():
                            ep_num = ep_num.zfill(2)
                    if play_page_url:
                        abs_url = response.urljoin(play_page_url)
                        entries.append({
                            'episode': ep_num,
                            'play_page_url': abs_url,
                        })

                if entries:
                    group_name = self._extract_group_name(group)
                    source_name = (
                        group_name or
                        (source_names[index] if index < len(source_names) else None) or
                        f'source-{index + 1}'
                    )
                    groups_data.append({
                        'source_name': source_name,
                        'anime_key': anime_key,
                        'entries': entries,
                    })

            if groups_data:
                break

        return self._dedupe_play_entry_groups(groups_data)

    def extract_play_sources_from_page(self, response):
        """从详情页/播放页提取多线路播放源。"""
        selector_groups = [
            ('.stui-pannel-box.b.playlist, .stui-pannel-box.playlist, .module-play-list', '.stui-content__playlist a, a.module-play-list-link, a'),
            ('.stui-content__playlist, .play-list, .playlist, .source-list', 'a'),
        ]

        source_names = self._extract_source_names(response)
        player_config = self.extract_player_config(response)
        play_sources = []
        anime_key = self._extract_anime_play_key(response.url)

        for group_selector, item_selector in selector_groups:
            groups = response.css(group_selector)
            if not groups:
                continue

            for index, group in enumerate(groups):
                episodes = []
                items = group.css(item_selector)
                for item in items:
                    ep_num = (
                        item.css('::attr(data-episode)').get() or
                        item.css('::attr(data-ep)').get() or
                        item.css('::text').get()
                    )
                    ep_url = item.css('::attr(href)').get()
                    if ep_num:
                        ep_num = re.sub(r'[^\d.]', '', ep_num) or None
                        if ep_num and ep_num.isdigit():
                            ep_num = ep_num.zfill(2)
                    if ep_url:
                        if anime_key and anime_key not in ep_url:
                            continue
                        abs_url = response.urljoin(ep_url)
                        if not self._is_playable_media_url(abs_url):
                            continue
                        episodes.append({
                            'episode': ep_num,
                            'url': abs_url,
                        })

                if episodes:
                    group_name = self._extract_group_name(group)
                    source_name = (
                        group_name or
                        (source_names[index] if index < len(source_names) else None) or
                        f'source-{index + 1}'
                    )
                    source = {
                        'source_name': source_name,
                        'domain': urlparse(response.url).netloc,
                        'episodes': episodes,
                        'quality': None,
                        'raw_url': response.url,
                    }
                    self._apply_player_metadata(source, player_config, index)
                    play_sources.append(source)

            if play_sources:
                break

        return self._dedupe_play_sources(play_sources)

    def _is_playable_media_url(self, url):
        if not url:
            return False
        lower = str(url).strip().lower()
        if any(ext in lower for ext in self.PLAYABLE_EXTENSIONS):
            return True
        return False

    def _extract_source_names(self, response):
        names = []
        for selector in self.SOURCE_NAME_SELECTORS:
            values = [text.strip() for text in response.css(selector).getall() if text and text.strip()]
            if values:
                names.extend([self._clean_source_name(value) for value in values if self._clean_source_name(value)])
                break
        return names

    def extract_player_config(self, response):
        """从播放页脚本中提取播放器配置。"""
        content = response.text or ''
        match = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', content, re.DOTALL | re.IGNORECASE)
        if not match:
            return {}

        raw = match.group(1).strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.debug('[M3U8Extractor] player_aaaa JSON 解析失败: %s', response.url)
            return {}

    def _extract_group_name(self, group):
        selectors = [
            '.stui-pannel__head h2.title::text',
            '.stui-pannel__head .title::text',
            '.title::text',
        ]
        for selector in selectors:
            values = [self._clean_source_name(value) for value in group.css(selector).getall() if value]
            values = [value for value in values if value]
            if values:
                return values[-1]
        return None

    def _apply_player_metadata(self, source, player_config, index):
        if not source:
            return source

        config = player_config or {}
        line_from = config.get('from')
        sid = config.get('sid')
        source_name = source.get('source_name')

        if line_from:
            source['line_from'] = str(line_from)
        if sid is not None:
            source['line_sid'] = str(sid)

        line_parts = [str(part).strip() for part in [line_from, sid, source_name] if part not in (None, '')]
        if line_parts:
            source['line_id'] = '|'.join(line_parts)
        anime_key = self._extract_anime_play_key(source.get('raw_url'))
        if anime_key:
            source['anime_key'] = anime_key

        provider_key = None
        player_url = config.get('url')
        if player_url:
            provider_key = urlparse(player_url).netloc.lower()
        elif line_from:
            provider_key = f'{urlparse(source.get("raw_url", "")).netloc.lower()}|{str(line_from).lower()}'

        if provider_key:
            source['provider_key'] = provider_key

        if not source_name or source_name.startswith('source-'):
            if line_from:
                source['source_name'] = str(line_from)
            elif sid is not None:
                source['source_name'] = f'line-{sid}'
            else:
                source['source_name'] = f'source-{index + 1}'
        return source

    def _clean_source_name(self, value):
        if not value:
            return None
        cleaned = re.sub(r'\s+', ' ', str(value)).strip()
        cleaned = cleaned.replace('无需安装任何插件', '').strip()
        return cleaned or None

    def _extract_anime_play_key(self, url):
        match = re.search(r'/(?:post|play)/(\d+)', url or '')
        return match.group(1) if match else None

    def _dedupe_play_sources(self, play_sources):
        deduped = {}
        for source in play_sources or []:
            episodes = source.get('episodes') or []
            episode_urls = tuple(sorted(str(ep.get('url')) for ep in episodes if ep.get('url')))
            if not episode_urls:
                continue

            key = episode_urls
            existing = deduped.get(key)
            if not existing:
                deduped[key] = source
                continue

            if self._source_rank(source) > self._source_rank(existing):
                deduped[key] = source

        return list(deduped.values())

    def _dedupe_play_entry_groups(self, groups_data):
        deduped = {}
        for group in groups_data or []:
            entries = group.get('entries') or []
            if not entries:
                continue

            entry_signature = tuple(
                (str(entry.get('episode') or ''), str(entry.get('play_page_url') or ''))
                for entry in entries
            )
            first_url = str(entries[0].get('play_page_url') or '')
            key = (
                len(entries),
                first_url,
                entry_signature[:8],
            )
            existing = deduped.get(key)
            if not existing:
                deduped[key] = group
                continue

            if self._entry_group_rank(group) > self._entry_group_rank(existing):
                deduped[key] = group

        return list(deduped.values())

    def _source_rank(self, source):
        score = 0
        name = str(source.get('source_name') or '').strip().lower()
        if name and not name.startswith('source-') and not name.startswith('legacy-'):
            score += 2
        if source.get('line_from'):
            score += 3
        if source.get('line_sid'):
            score += 2
        if source.get('provider_key'):
            score += 2
        return score

    def _entry_group_rank(self, group):
        score = 0
        name = str((group or {}).get('source_name') or '').strip().lower()
        if name and not name.startswith('source-'):
            score += 2
        if name and ('路线' in name or '线路' in name or '高清' in name or '百度' in name or 'bf' in name.lower()):
            score += 1
        return score
