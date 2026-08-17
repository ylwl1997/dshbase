#!/usr/bin/env python3
"""部署后向 IndexNow 提交 sitemap 全量 URL，通知 Bing 等搜索引擎即时收录。

IndexNow key 文件在 public/<KEY>.txt（部署后即 https://dshbase.com/<KEY>.txt）。
用法：python3 scripts/indexnow-ping.py
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SITEMAP = os.path.join(ROOT, 'public', 'sitemap.xml')
HOST = 'dshbase.com'
KEY = '936fa69bd8459c95783c9200f2932d6a'
ENDPOINT = 'https://api.indexnow.org/indexnow'
MAX_BATCH = 10000


def read_urls():
    if not os.path.exists(SITEMAP):
        print('IndexNow: sitemap 不存在，跳过')
        return []
    txt = open(SITEMAP, encoding='utf-8').read()
    return re.findall(r'<loc>\s*([^<]+?)\s*</loc>', txt)


def ping(urls):
    if not urls:
        print('IndexNow: 无 URL，跳过')
        return
    for i in range(0, len(urls), MAX_BATCH):
        batch = urls[i:i + MAX_BATCH]
        body = json.dumps({
            'host': HOST,
            'key': KEY,
            'keyLocation': f'https://{HOST}/{KEY}.txt',
            'urlList': batch,
        }).encode('utf-8')
        req = urllib.request.Request(ENDPOINT, data=body, headers={
            'Content-Type': 'application/json; charset=utf-8',
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                print(f'IndexNow: 已提交 {len(batch)} 个 URL -> HTTP {r.status}')
        except urllib.error.HTTPError as e:
            print(f'IndexNow: HTTP {e.code} {e.read().decode("utf-8", "replace")[:200]}')
        except Exception as e:
            print(f'IndexNow: 提交失败 {e}')


if __name__ == '__main__':
    urls = read_urls()
    print(f'IndexNow: sitemap 共 {len(urls)} 个 URL')
    ping(urls)
