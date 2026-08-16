#!/usr/bin/env python3
"""从 plugins.json 生成 functions/badges/data.js（徽章端点数据源）。

徽章端点 /badges/<name>.svg 需要一个 name -> test 状态的快速查找表，
不依赖 Node 运行时读 plugins.json（functions 运行在 Cloudflare Workers 环境）。
"""
import json
import os

DB = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'data', 'plugins.json'))
OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'functions', 'badges', 'data.js'))


def main():
    d = json.load(open(DB, encoding='utf-8'))
    allp = [p for items in d.values() for p in items]
    # name -> test 状态（verified / pending）
    m = {p['name']: p.get('test') for p in allp}
    js = 'export default ' + json.dumps(m, ensure_ascii=False, separators=(',', ':')) + ';\n'
    open(OUT, 'w', encoding='utf-8').write(js)
    nv = sum(1 for v in m.values() if v == 'verified')
    print(f'badges data.js: {len(m)} plugins ({nv} verified) -> {OUT}')


if __name__ == '__main__':
    main()
