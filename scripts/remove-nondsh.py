#!/usr/bin/env python3
"""汇总三处审计产物，从 plugins.json 移除确凿非 DSH 插件。
来源: audit-tagsquat.txt(无DSH标记) + audit-tagsquat-recheck.txt(DROP) + 7个SKILL.md无DSH引用
输出: 打印每个被移除插件的 name/repo/category，写 removed-112.txt 备查。
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'src', 'data', 'plugins.json')
OUT = os.path.join(ROOT, 'removed-112.txt')

# 7 个 SKILL.md 无 DSH 引用（本次人工判定非 DSH）
SKILL_ONLY_DROP = {
    'phoenixlucky/zerotoken-skill',
    'ginuim/multi-screen-wireframe',
    'kuangre123/iosdev',
    'dqsjqian/agent-guild',
    'remybroun/infographic',
    'phoenixlucky/chrome-mcp-bridge-2026-skill',
    't1yos/t1y-skills',
}

drop = set()

# 1) audit-tagsquat.txt: name\tkey\tcat\t★stars\twhy  (why=无DSH标记)
for line in open(os.path.join(ROOT, 'audit-tagsquat.txt'), encoding='utf-8'):
    line = line.rstrip('\n')
    if not line or '\t无DSH标记' not in line:
        continue
    parts = line.split('\t')
    drop.add(parts[1].lower())

# 2) audit-tagsquat-recheck.txt: DROP\tname\tkey\tcat\tstars\twhy
for line in open(os.path.join(ROOT, 'audit-tagsquat-recheck.txt'), encoding='utf-8'):
    line = line.rstrip('\n')
    if not line.startswith('DROP\t'):
        continue
    parts = line.split('\t')
    drop.add(parts[2].lower())

# 3) SKILL.md 无 DSH 引用
drop |= {k.lower() for k in SKILL_ONLY_DROP}

print(f'待删 repo key 集合: {len(drop)} 个')

d = json.load(open(DATA, encoding='utf-8'))
URL = re.compile(r'github\.com/([^/]+/[^/]+?)(?:/|$)', re.I)

removed = []
for cat, items in d.items():
    keep = []
    for p in items:
        m = URL.search(p.get('url') or '')
        key = m.group(1).rstrip('.git').lower() if m else ''
        if key in drop:
            removed.append((cat, p.get('name'), p.get('url'), key))
        else:
            keep.append(p)
    d[cat] = keep

# 统计 + 写回
before = sum(len(v) for v in d.values())
total_before = sum(1 for cat in d for _ in d[cat]) + len(removed)

print(f'移除 {len(removed)} 个插件（drop 集合 {len(drop)} 个）')

json.dump(d, open(DATA, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

from collections import Counter
bycat = Counter(c for c, *_ in removed)
print('\n按分类统计:')
for c, n in bycat.most_common():
    print(f'  {c}: {n}')

with open(OUT, 'w', encoding='utf-8') as f:
    for cat, name, url, key in sorted(removed, key=lambda x: x[1].lower()):
        f.write(f'{name}\t{key}\t{cat}\n')

print('\n被移除插件清单:')
for cat, name, url, key in sorted(removed, key=lambda x: x[1].lower()):
    print(f'  [{cat}] {name}  ({key})')

print(f'\n移除后插件总数: {sum(len(v) for v in d.values())}')
