#!/usr/bin/env python3
"""从 plugins.json 重新生成 functions/api/repos.js（实时星数数据源）。

只保留按 stars 前 240 的仓库（实时星数只对热门插件有价值，长尾用每日刷新的静态值）。
"""
import json
import os
import re

DB = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'data', 'plugins.json'))
OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'functions', 'api', 'repos.js'))
TOP = 240


def main():
    d = json.load(open(DB, encoding='utf-8'))
    allp = [p for items in d.values() for p in items]
    repos = []
    seen = set()
    for p in allp:
        m = re.search(r'github\.com/([^/]+)/([^/]+?)/?$', p.get('url') or '')
        if not m:
            continue
        key = (m.group(1), m.group(2).removesuffix('.git'))
        if key in seen:
            continue
        seen.add(key)
        repos.append({'slug': p.get('slug') or p['name'], 'owner': key[0], 'repo': key[1], 'stars': p.get('stars') or 0})
    repos.sort(key=lambda r: -r['stars'])
    top = repos[:TOP]
    out = [{'slug': r['slug'], 'owner': r['owner'], 'repo': r['repo']} for r in top]
    js = 'export default ' + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + ';\n'
    open(OUT, 'w', encoding='utf-8').write(js)
    print(f'repos.js: top {len(out)} 仓库 -> {OUT}')


if __name__ == '__main__':
    main()
