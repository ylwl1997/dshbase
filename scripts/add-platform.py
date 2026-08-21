#!/usr/bin/env python3
"""Add a `platform` field to every plugin in plugins.json.

Default is "any" (cross-platform). A small curated map tags the platform-
exclusive plugins whose Linux-CI "verified" would otherwise be misleading.
Re-runnable: only sets the field where it is missing / differs from the map.
"""
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB = os.path.join(ROOT, 'src', 'data', 'plugins.json')

# name -> platform for platform-exclusive plugins (keyed by unique name)
CURATED = {
    'dsh-win32': 'win32',
    'dsh-windows-ocr': 'win32',
    'dsh-bash-terminal': 'win32',
    'dsh-web-app-launcher': 'win32',
    'dsh-mac-vision': 'macos',
}

d = json.load(open(DB, encoding='utf-8'))
tagged = 0
for cat, items in d.items():
    for p in items:
        pf = CURATED.get(p.get('name'))
        if pf is None:
            pf = p.get('platform') or 'any'
        if p.get('platform') != pf:
            p['platform'] = pf
            tagged += 1

json.dump(d, open(DB, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

from collections import Counter
c = Counter()
for items in d.values():
    for p in items:
        c[p.get('platform')] += 1
print(f'platform set (changed {tagged}): {dict(c)}')
