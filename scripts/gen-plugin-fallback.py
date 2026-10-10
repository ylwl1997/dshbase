#!/usr/bin/env python3
"""Write functions/_data/plugin-fallback.js for on-demand Pages Function plugin pages."""
import json, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
plugins = json.load(open(os.path.join(ROOT, 'src/data/plugins.json'), encoding='utf-8'))
idx = json.load(open(os.path.join(ROOT, 'src/data/indexable-plugins.json'), encoding='utf-8'))
en_i, zh_i = set(idx.get('en') or []), set(idx.get('zh') or [])
BULK = '2026-10-10'

def ssg_en(p):
  slug = p.get('slug') or p['name']
  return int(p.get('stars') or 0) >= 10 or slug in en_i or (p.get('added') or '') < BULK

def ssg_zh(p):
  slug = p.get('slug') or p['name']
  return slug in zh_i or ((p.get('added') or '') < BULK and bool((p.get('desc_zh') or '').strip()))

out = {}
for cat, items in plugins.items():
  for p in items:
    if ssg_en(p) and ssg_zh(p):
      continue
    slug = p.get('slug') or p['name']
    out[slug] = {
      'slug': slug, 'name': p['name'], 'url': p.get('url') or '', 'pkg': p.get('pkg') or '',
      'npm': bool(p.get('npm') and p.get('pkg')), 'test': p.get('test') or 'verified',
      'desc': (p.get('desc_en') or p.get('desc') or '')[:400],
      'desc_zh': (p.get('desc_zh') or '')[:400],
      'stars': int(p.get('stars') or 0), 'cat': cat,
      'ssg_en': ssg_en(p), 'ssg_zh': ssg_zh(p),
    }
dest = os.path.join(ROOT, 'functions', '_data', 'plugin-fallback.js')
os.makedirs(os.path.dirname(dest), exist_ok=True)
with open(dest, 'w', encoding='utf-8') as f:
  f.write('export default ')
  json.dump(out, f, ensure_ascii=False)
  f.write(';\n')
print(f'fallback {len(out)} -> {dest}')
