#!/usr/bin/env python3
"""合并 verify-all.sh 的多个结果 TSV，写回 plugins.json。

保守策略：只升级为 verified；install-fail 且非 verified 才标 pending（未测试）；load-fail/network-fail 不动。
多次结果取「最好」的（ok > load-fail > install-fail > network-fail）。
用法：python scripts/merge-verify.py result1.tsv result2.tsv ...
"""
import json
import sys

DATA = 'src/data/plugins.json'
ORDER = {'ok': 0, 'load-fail': 1, 'runtime-fail': 2, 'install-fail': 3, 'network-fail': 4}
# 严格标准：只有 ok 升级 verified；安装/加载/运行时任一失败都视为未通过验证 → pending
FAIL_STATES = {'install-fail', 'load-fail', 'runtime-fail'}


def main(files):
    res = {}
    for f in files:
        for line in open(f, encoding='utf-8'):
            line = line.strip()
            if not line:
                continue
            parts = line.split('\t', 1)
            if len(parts) != 2:
                continue
            name, status = parts
            prev = res.get(name)
            if prev is None or ORDER.get(status, 9) < ORDER.get(prev, 9):
                res[name] = status

    d = json.load(open(DATA, encoding='utf-8'))
    upgraded = pending = skipped = 0
    for items in d.values():
        for p in items:
            st = res.get(p['name'])
            if not st:
                continue
            old = p.get('test')
            if st == 'ok' and old != 'verified':
                p['test'] = 'verified'
                upgraded += 1
            elif st in FAIL_STATES and old != 'verified' and old != 'pending':
                p['test'] = 'pending'
                pending += 1
            else:
                skipped += 1
    json.dump(d, open(DATA, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'merged {len(res)} results: verified +{upgraded}, pending +{pending}, skipped {skipped}')


if __name__ == '__main__':
    main(sys.argv[1:])
