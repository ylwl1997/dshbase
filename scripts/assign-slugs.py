#!/usr/bin/env python3
"""为每个插件分配唯一 slug（同名不同仓库的插件用 -N 后缀消歧）。

背景：dsh.so 目录里存在大量「同名不同仓」的插件（如 dsh-desktop 有 16 个不同仓库，
deepseek-harness-desktop 有 13 个）。我们站点以 name 作为 URL slug，同名会撞页。
这里给每个插件加 `slug` 字段：该名字下第一个（verified 优先、stars 降序）保持原名，
其余依次加 -2 / -3 / ... 后缀，保证全局唯一。URL / 徽章 / 站点地图改用 slug。

用法：python scripts/assign-slugs.py
"""
import json
import os
from collections import defaultdict

DB = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'data', 'plugins.json'))


def main():
    d = json.load(open(DB, encoding='utf-8'))
    by_name = defaultdict(list)
    for cat, items in d.items():
        for p in items:
            by_name[p['name']].append((cat, p))

    for name, group in by_name.items():
        # verified 优先，然后 stars 降序，最后 url 稳定（保证多次运行结果一致）
        group.sort(key=lambda cp: (
            0 if cp[1].get('test') == 'verified' else 1,
            -(cp[1].get('stars') or 0),
            cp[1].get('url') or '',
        ))
        for i, (cat, p) in enumerate(group):
            p['slug'] = name if i == 0 else f'{name}-{i + 1}'

    json.dump(d, open(DB, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    total = sum(len(v) for v in d.values())
    uniq = len({p['slug'] for items in d.values() for p in items})
    dup = sum(1 for v in by_name.values() if len(v) > 1)
    print(f'slug 分配完成：{total} 插件 / {uniq} 唯一 slug / {dup} 组同名')


if __name__ == '__main__':
    main()
