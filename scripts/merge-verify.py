#!/usr/bin/env python3
"""合并 verify-runtime.sh 的结果 TSV，写回 plugins.json。

判定：ok 升级 verified；web-only（安装+加载通过、但 headless 缺 GUI 服务、L3 未验证）保持 pending
并打 webonly 标记，待 web 运行时复测；install-fail/load-fail/runtime-fail 保持/降为 pending。
多次结果取「最好」的（ok > web-only > load-fail > runtime-fail > install-fail > network-fail）。
用法：python scripts/merge-verify.py result1.tsv result2.tsv ...
"""
import json
import sys

DATA = 'src/data/plugins.json'
ORDER = {'ok': 0, 'web-only': 1, 'load-fail': 2, 'runtime-fail': 3, 'install-fail': 4, 'network-fail': 5}
# 严格标准：只有 ok 升级 verified。web-only = 安装+加载通过、但 headless 缺 GUI 服务（L3 未验证），
# 不算 verified，保持 pending 并打 webonly 标记。安装/加载/运行时任一失败 → pending。
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
    upgraded = pending = webonly = skipped = 0
    for items in d.values():
        for p in items:
            st = res.get(p['name'])
            if not st:
                continue
            old = p.get('test')
            if st == 'ok':
                if old != 'verified':
                    p['test'] = 'verified'
                    upgraded += 1
            elif st == 'web-only':
                # 安装+加载通过，但 headless 缺 GUI 服务（webServer/storage/workspace 等），L3 未验证。
                # 不算 verified，保持 pending 并打 webonly 标记，待 web 运行时复测。
                p['webonly'] = True
                if old != 'pending':
                    p['test'] = 'pending'
                    pending += 1
                webonly += 1
            elif st in FAIL_STATES and old != 'verified' and old != 'pending':
                p['test'] = 'pending'
                pending += 1
            else:
                skipped += 1
    json.dump(d, open(DATA, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'merged {len(res)} results: verified +{upgraded}, web-only +{webonly}, pending +{pending}, skipped {skipped}')


if __name__ == '__main__':
    main(sys.argv[1:])
