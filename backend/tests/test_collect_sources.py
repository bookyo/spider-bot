#!/usr/bin/env python3
"""测试采集引擎的两个资源站接口"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.env import load_backend_env
load_backend_env()

from api.database import connect, close
from services.collect_engine import CollectEngine, download_poster_with_retry

async def test_source(engine, source_config, label):
    print(f'\n{"="*60}')
    print(f'测试: {label}')
    print(f'URL: {source_config["url"]}')
    print(f'类型: {source_config["type"]}')
    print(f'{"="*60}')

    # 测试列表获取
    print('\n[1] 拉取列表 (page=1, hours=24)...')
    try:
        list_data = await engine.fetch_list(source_config, page=1, hours=24)
        items = list_data.get('list', [])
        types_list = list_data.get('types', [])
        print(f'    列表: {len(items)} 条, 类型: {len(types_list)} 个')
        print(f'    分页: page={list_data.get("page")}, pagecount={list_data.get("pagecount")}, total={list_data.get("total")}')
        if types_list:
            print(f'    类型示例: {types_list[:3]}')

        if items:
            print(f'\n    前2条数据:')
            for i, item in enumerate(items[:2]):
                print(f'    [{i+1}] vid={item.get("vod_id") or item.get("id")}, name={item.get("vod_name") or item.get("name")}')
                print(f'        time={item.get("vod_time") or item.get("last")}, remarks={item.get("vod_remarks") or item.get("note")}')
                has_play = item.get('vod_play_url') or item.get('play_url')
                print(f'        has_play_url={bool(has_play)}, play_from={item.get("vod_play_from")}')

            # 测试详情获取
            ids_for_detail = []
            for item in items[:3]:
                has_play = item.get('vod_play_url') or item.get('play_url')
                if not has_play:
                    vid = str(item.get('vod_id') or item.get('id') or '').strip()
                    if vid:
                        ids_for_detail.append(vid)

            if ids_for_detail:
                print(f'\n[2] 拉取详情 ids={ids_for_detail}...')
                details = await engine.fetch_detail(source_config, ids_for_detail)
                print(f'    详情: {len(details)} 条')
                for d in details[:1]:
                    print(f'    vid={d.get("vod_id") or d.get("id")}, name={d.get("vod_name") or d.get("name")}')
                    pic = d.get('vod_pic') or d.get('pic') or ''
                    play_url = d.get('vod_play_url') or d.get('play_url') or ''
                    print(f'    pic={pic[:100] if pic else "N/A"}')
                    print(f'    play_url_len={len(play_url)}')
                    # 测试 normalize
                    normalized = engine.normalize(d, source_config)
                    print(f'    normalized: title={normalized.get("title")}')
                    print(f'    poster_url={normalized.get("poster_url","")[:80]}')
                    print(f'    play_sources={len(normalized.get("play_sources",[]))} 个')
                    for ps in normalized.get('play_sources', []):
                        print(f'      source={ps.get("source_name")}, episodes={len(ps.get("episodes",[]))}')

            # 测试海报下载
            if items:
                test_item = items[0]
                # 如果有详情，合并后用
                detail_for_test = None
                for d in (details if ids_for_detail else []):
                    if str(d.get('vod_id') or d.get('id') or '') == str(test_item.get('vod_id') or test_item.get('id') or ''):
                        detail_for_test = d
                        break
                if detail_for_test:
                    test_item = {**test_item, **detail_for_test}

                normalized = engine.normalize(test_item, source_config)
                poster_url = normalized.get('poster_url', '')
                dedup_key = normalized.get('dedup_key', '')
                if poster_url:
                    print(f'\n[3] 测试海报下载: {poster_url[:100]}...')
                    local = await download_poster_with_retry(poster_url, dedup_key)
                    print(f'    结果: {local}')
                else:
                    print(f'\n[3] 无海报URL，跳过下载测试')
        else:
            print('    列表为空!')
    except Exception as e:
        print(f'    错误: {e}')
        import traceback
        traceback.print_exc()

async def main():
    print('连接数据库...')
    await connect()

    engine = CollectEngine()

    # 测试源1: 360zy (JSON)
    await test_source(engine, {
        'url': 'https://360zy.com/api.php/provide/vod',
        'type': 'json',
        'mid': 1,
        'appid': '',
        'appkey': '',
        'bind': False,
        'status': True,
    }, '360zy (JSON)')

    # 测试源2: ffzyapi (XML)
    await test_source(engine, {
        'url': 'http://api.ffzyapi.com/api.php/provide/vod/from/ffm3u8/at/xml/',
        'type': 'xml',
        'mid': 1,
        'appid': '',
        'appkey': '',
        'bind': False,
        'status': True,
    }, 'ffzyapi (XML)')

    await engine.close()
    await close()
    print('\n测试完成!')

if __name__ == '__main__':
    asyncio.run(main())
