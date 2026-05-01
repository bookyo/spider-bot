"""域名自动发现工具 - 通过 crt.sh / Whois / DNS 枚举发现动漫网站"""

import re
import json
import logging
import dns.resolver
import requests
from urllib.parse import urlparse
from datetime import datetime, timedelta
from config.keywords import ANIME_SITE_KEYWORDS
from config.sites import EXCLUDED_DOMAINS

logger = logging.getLogger(__name__)


class DomainDiscover:
    """域名发现器"""

    def __init__(self):
        self.discovered_domains = set()

    def discover_all(self, methods=None):
        """运行所有发现方法"""
        if methods is None:
            methods = ['crt_sh', 'dns_enum']

        results = set()

        if 'crt_sh' in methods:
            crt_domains = self.discover_from_crt_sh()
            results.update(crt_domains)

        if 'dns_enum' in methods:
            dns_domains = self.discover_from_dns_enum()
            results.update(dns_domains)

        # 过滤排除的域名
        filtered = self._filter_domains(results)
        self.discovered_domains.update(filtered)

        logger.info(f'[DomainDiscover] 共发现 {len(filtered)} 个新域名')
        return filtered

    def discover_from_crt_sh(self):
        """从证书透明度日志发现域名"""
        from config.settings import CRT_SH_QUERIES

        domains = set()
        logger.info('[DomainDiscover] 开始查询 crt.sh 证书透明度日志...')

        for query in CRT_SH_QUERIES:
            try:
                url = f'https://crt.sh/?q={query}&output=json'
                response = requests.get(url, timeout=30)

                if response.status_code == 200:
                    try:
                        entries = response.json()
                    except json.JSONDecodeError:
                        logger.warning(f'[crt.sh] JSON 解析失败: {query}')
                        continue

                    for entry in entries:
                        name = entry.get('name_value', '')
                        # 可能包含多个域名（换行分隔）
                        for domain_name in name.split('\n'):
                            domain_name = domain_name.strip().lower()
                            # 去掉通配符
                            domain_name = domain_name.replace('*.', '')
                            # 只保留有效域名
                            if self._is_valid_domain(domain_name):
                                domains.add(domain_name)

                    logger.info(f'[crt.sh] 查询 "{query}" 发现 {len(domains)} 个域名')
                else:
                    logger.warning(f'[crt.sh] 请求失败: {response.status_code}')

            except Exception as e:
                logger.error(f'[crt.sh] 请求异常: {e}')
                continue

        logger.info(f'[crt.sh] 共发现 {len(domains)} 个域名')
        return domains

    def discover_from_dns_enum(self, base_domains=None):
        """DNS 枚举 - 子域名发现"""
        from config.settings import DNS_ENUM_PREFIXES

        if not base_domains:
            # 从数据库获取已知的动漫站点域名
            base_domains = self._get_known_base_domains()

        domains = set()
        logger.info(f'[DNS Enum] 开始枚举 {len(base_domains)} 个基础域名的子域名...')

        for base_domain in base_domains:
            for prefix in DNS_ENUM_PREFIXES:
                subdomain = f'{prefix}.{base_domain}'
                try:
                    dns.resolver.resolve(subdomain, 'A')
                    domains.add(subdomain)
                    logger.debug(f'[DNS Enum] 发现子域名: {subdomain}')
                except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
                    pass
                except Exception as e:
                    logger.debug(f'[DNS Enum] 查询异常 {subdomain}: {e}')

        logger.info(f'[DNS Enum] 共发现 {len(domains)} 个子域名')
        return domains

    def discover_from_whois(self, keywords=None):
        """通过 Whois 查询发现新注册域名

        注意：此方法需要第三方 Whois API 服务支持，
        免费服务有查询限制，建议配合其他方法使用。
        """
        if keywords is None:
            from config.settings import WHOIS_KEYWORDS
            keywords = WHOIS_KEYWORDS

        domains = set()
        logger.info('[Whois] Whois 新域名监控（需要 API 服务支持）...')

        # 这里可以集成第三方 Whois API
        # 例如：WhoisXML API, SecurityTrails, etc.
        # 免费额度有限，建议作为补充手段

        # 示例：通过 SecurityTrails API 查询
        # api_key = os.environ.get('SECURITYTRAILS_API_KEY')
        # if api_key:
        #     for keyword in keywords:
        #         url = f'https://api.securitytrails.com/v1/search/list'
        #         headers = {'apikey': api_key}
        #         params = {'keyword': keyword, 'page': 0}
        #         resp = requests.post(url, json=params, headers=headers)
        #         if resp.status_code == 200:
        #             data = resp.json()
        #             for record in data.get('records', []):
        #                 domains.add(record.get('hostname', ''))

        logger.info(f'[Whois] 发现 {len(domains)} 个域名')
        return domains

    def verify_anime_site(self, domain, timeout=10):
        """验证域名是否为动漫站点"""
        urls_to_check = [
            f'https://{domain}',
            f'http://{domain}',
        ]

        for url in urls_to_check:
            try:
                response = requests.get(url, timeout=timeout, allow_redirects=True, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })

                if response.status_code == 200:
                    content = response.text.lower()
                    # 检查是否包含动漫相关关键词
                    keyword_count = sum(1 for kw in ANIME_SITE_KEYWORDS if kw.lower() in content)

                    if keyword_count >= 2:
                        logger.info(f'[验证] {domain} 是动漫站点 (关键词匹配: {keyword_count})')
                        return True

                    # 检查 URL 路径模式
                    from config.keywords import ANIME_URL_PATTERNS
                    url_matches = sum(1 for pattern in ANIME_URL_PATTERNS if re.search(pattern, content))
                    if url_matches >= 3:
                        logger.info(f'[验证] {domain} 可能是动漫站点 (URL模式匹配: {url_matches})')
                        return True

            except Exception:
                continue

        logger.debug(f'[验证] {domain} 不是动漫站点')
        return False

    def _is_valid_domain(self, domain):
        """检查是否为有效域名"""
        if not domain or len(domain) > 253:
            return False
        # 排除 IP 地址
        if re.match(r'^\d+\.\d+\.\d+\.\d+$', domain):
            return False
        # 排除无效字符
        if not re.match(r'^[a-z0-9][a-z0-9.-]+\.[a-z]{2,}$', domain):
            return False
        # 排除已知的非动漫域名
        for excluded in EXCLUDED_DOMAINS:
            if excluded in domain:
                return False
        return True

    def _filter_domains(self, domains):
        """过滤域名列表"""
        filtered = set()
        for domain in domains:
            domain = domain.lower().strip()
            if self._is_valid_domain(domain):
                filtered.add(domain)
        return filtered

    def _get_known_base_domains(self):
        """从数据库获取已知的动漫站点基础域名"""
        try:
            from anime_spider.utils.db import MongoDB
            domain_col = MongoDB.get_domain_collection()
            domains = domain_col.distinct('domain', {'is_anime_site': True})
            # 提取基础域名
            base_domains = set()
            for d in domains:
                parts = d.split('.')
                if len(parts) >= 2:
                    base_domains.add('.'.join(parts[-2:]))
            return list(base_domains)
        except Exception:
            return []
