#!/usr/bin/env python3
"""动漫爬虫启动入口

使用方法:
    # 域名发现
    python run.py discover

    # 爬取指定域名
    python run.py crawl -d example.com

    # 爬取指定 URL
    python run.py crawl -u https://example.com/anime/123

    # 完整流程（发现 + 爬取）
    python run.py full
"""

import sys
import os
import argparse
import logging
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings


def setup_logging():
    """配置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )


def run_discover(methods=None):
    """运行域名发现"""
    from anime_spider.spiders.discover_spider import DiscoverSpider

    settings = get_project_settings()
    process = CrawlerProcess(settings)

    kwargs = {}
    if methods:
        kwargs['methods'] = methods

    process.crawl(DiscoverSpider, **kwargs)
    process.start()


def run_crawl(domain=None, url=None, max_depth=3, search_discovery=False, search_pagination_max_pages=200):
    """运行站点爬虫"""
    from anime_spider.spiders.site_spider import SiteSpider

    settings = get_project_settings()
    process = CrawlerProcess(settings)

    kwargs = {
        'max_depth': max_depth,
        'search_discovery': search_discovery,
        'search_pagination_max_pages': search_pagination_max_pages,
    }
    if domain:
        kwargs['domain'] = domain
    elif url:
        kwargs['url'] = url

    process.crawl(SiteSpider, **kwargs)
    process.start()


def run_incremental(limit=20, min_hours=6):
    """运行按动画候选排序的增量巡检。"""
    from anime_spider.spiders.site_spider import SiteSpider
    from anime_spider.utils.db import MongoDB
    from anime_spider.utils.incremental_scheduler import IncrementalScheduler

    settings = get_project_settings()
    process = CrawlerProcess(settings)

    try:
        anime_col = MongoDB.get_anime_collection()
        scheduler = IncrementalScheduler()
        candidates = []

        for doc in anime_col.find({'source_urls.0': {'$exists': True}}):
            if scheduler.should_check(doc, min_hours=min_hours):
                candidates.append(doc)

        candidates.sort(key=lambda doc: scheduler.score(doc), reverse=True)
        selected = candidates[:limit]

        if not selected:
            print('没有需要增量巡检的动画')
            return

        print(f'准备增量巡检 {len(selected)} 条动画')
        for doc in selected:
            targets = scheduler.build_targets(doc)
            if not targets:
                continue
            primary = targets[0]
            print(
                f"[增量] {doc.get('title') or doc.get('_id')} -> "
                f"{primary['kind']} {primary['url']}"
            )
            process.crawl(SiteSpider, url=primary['url'], max_depth=1, incremental_mode=True)

        process.start()
    except Exception as e:
        print(f'增量巡检失败: {e}')
    finally:
        MongoDB.close()


def run_full(methods=None, max_depth=3):
    """运行完整流程（发现 + 爬取）"""
    from anime_spider.spiders.discover_spider import DiscoverSpider
    from anime_spider.spiders.site_spider import SiteSpider
    from anime_spider.utils.db import MongoDB
    from anime_spider.utils.domain_priority import DomainPriorityScorer

    settings = get_project_settings()

    # 第一步：域名发现
    print('=' * 60)
    print(f'[{datetime.now()}] 第一步：域名发现')
    print('=' * 60)

    process = CrawlerProcess(settings)
    kwargs = {}
    if methods:
        kwargs['methods'] = methods
    process.crawl(DiscoverSpider, **kwargs)
    process.start()

    # 第二步：爬取发现的域名
    print('=' * 60)
    print(f'[{datetime.now()}] 第二步：爬取发现的域名')
    print('=' * 60)

    # 从数据库获取待爬取的域名
    try:
        domain_col = MongoDB.get_domain_collection()
        pending_docs = list(domain_col.find({
            'is_anime_site': True,
            'status': 'pending',
        }))

        scorer = DomainPriorityScorer()
        pending_docs.sort(
            key=lambda doc: scorer.score(doc),
            reverse=True,
        )
        pending_domains = [doc['domain'] for doc in pending_docs]

        if not pending_domains:
            print('没有待爬取的域名')
            return

        print(f'发现 {len(pending_domains)} 个待爬取的域名')

        process = CrawlerProcess(settings)
        for domain in pending_domains:
            process.crawl(SiteSpider, domain=domain, max_depth=max_depth)

        process.start()

    except Exception as e:
        print(f'获取待爬取域名失败: {e}')
    finally:
        MongoDB.close()


def main():
    parser = argparse.ArgumentParser(description='动漫爬虫')
    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # discover 命令
    discover_parser = subparsers.add_parser('discover', help='域名发现')
    discover_parser.add_argument(
        '-m', '--methods',
        help='发现方法，逗号分隔 (crt_sh,whois,dns_enum)',
        default=None,
    )

    # crawl 命令
    crawl_parser = subparsers.add_parser('crawl', help='爬取指定站点')
    crawl_group = crawl_parser.add_mutually_exclusive_group(required=True)
    crawl_group.add_argument('-d', '--domain', help='目标域名')
    crawl_group.add_argument('-u', '--url', help='目标 URL')
    crawl_parser.add_argument(
        '--max-depth',
        type=int,
        default=3,
        help='最大爬取深度 (默认: 3)',
    )
    crawl_parser.add_argument(
        '--search-discovery',
        action='store_true',
        help='搜索页发现模式：只追详情页和搜索分页，不做全站扩散',
    )
    crawl_parser.add_argument(
        '--search-pagination-max-pages',
        type=int,
        default=200,
        help='搜索页最多追多少个分页，0 表示不限制',
    )

    incremental_parser = subparsers.add_parser('incremental', help='按动画候选执行增量巡检')
    incremental_parser.add_argument(
        '--limit',
        type=int,
        default=20,
        help='最多巡检多少条动画 (默认: 20)',
    )
    incremental_parser.add_argument(
        '--min-hours',
        type=int,
        default=6,
        help='距上次巡检至少多少小时才重查 (默认: 6)',
    )

    # full 命令
    full_parser = subparsers.add_parser('full', help='完整流程（发现 + 爬取）')
    full_parser.add_argument(
        '-m', '--methods',
        help='发现方法，逗号分隔',
        default=None,
    )
    full_parser.add_argument(
        '--max-depth',
        type=int,
        default=3,
        help='最大爬取深度 (默认: 3)',
    )

    args = parser.parse_args()
    setup_logging()

    if args.command == 'discover':
        run_discover(args.methods)
    elif args.command == 'crawl':
        run_crawl(args.domain, args.url, args.max_depth, args.search_discovery, args.search_pagination_max_pages)
    elif args.command == 'incremental':
        run_incremental(args.limit, args.min_hours)
    elif args.command == 'full':
        run_full(args.methods, args.max_depth)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
