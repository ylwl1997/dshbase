#!/usr/bin/env python3
"""合并 verify-runtime.sh（L1–L3 headless）结果 TSV，写回 plugins.json。

判定：
  ok        → verified（headless L3 已过，无需 L4）
  web-only  → 保持 pending + webonly=True + note「待 L4」
              （MUST 再跑 verify-webonly.sh / verify-full.sh 的 L4；只有 L4 ok 才 verified）
  *-fail    → pending + 失败 note

多次结果取「最好」的（ok > web-only > load-fail > runtime-fail > install-fail > network-fail）。
用法：python scripts/merge-verify.py result1.tsv result2.tsv ...
完整流水线：bash scripts/verify-full.sh 然后 merge-verify + merge-webonly。
"""
import json
import sys
from datetime import date

DATA = 'src/data/plugins.json'
ORDER = {'ok': 0, 'web-only': 1, 'load-fail': 2, 'runtime-fail': 3, 'install-fail': 4, 'network-fail': 5}
# 严格标准：headless ok → verified。web-only 不算过关，必须 L4（web CDP）后再由 merge-webonly 升级。
FAIL_STATES = {'install-fail', 'load-fail', 'runtime-fail', 'network-fail'}


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

    today = date.today().isoformat()
    d = json.load(open(DATA, encoding='utf-8'))
    upgraded = pending = webonly = skipped = 0
    for items in d.values():
        for p in items:
            st = res.get(p['name'])
            if not st:
                continue
            old = p.get('test')
            if st == 'ok':
                p['test'] = 'verified'
                p['testDate'] = today
                p.pop('webonly', None)
                # drop prior failure notes
                note = p.get('note') or ''
                if note.startswith('验证:') or '；验证:' in note:
                    p.pop('note', None)
                if old != 'verified':
                    upgraded += 1
            elif st == 'web-only':
                # L3 headless 判定为 GUI/web 插件：不算 verified，必须跑 L4（verify-webonly CDP）。
                p['webonly'] = True
                p['test'] = 'pending'
                p['testDate'] = today
                p['note'] = '验证: web-only；待 L4 web CDP'
                webonly += 1
                if old != 'pending':
                    pending += 1
            elif st in FAIL_STATES:
                if old == 'verified':
                    skipped += 1
                    continue
                p['test'] = 'pending'
                p['testDate'] = today
                p['note'] = f'验证: {st}'
                pending += 1
            else:
                skipped += 1
    json.dump(d, open(DATA, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'merged {len(res)} results: verified +{upgraded}, web-only +{webonly}, pending +{pending}, skipped {skipped}')


if __name__ == '__main__':
    main(sys.argv[1:])
