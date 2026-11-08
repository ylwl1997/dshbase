#!/usr/bin/env python3
"""Write functions/_data/plugin-fallback.js for on-demand Pages Function plugin pages."""
import json, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
plugins = json.load(open(os.path.join(ROOT, 'src/data/plugins.json'), encoding='utf-8'))
idx = json.load(open(os.path.join(ROOT, 'src/data/indexable-plugins.json'), encoding='utf-8'))
en_i, zh_i = set(idx.get('en') or []), set(idx.get('zh') or [])
BULK = '2026-10-10'

def later_bulk_listed(p):
  # Mirrors src/lib/ssg-plugins.js. Bulk listed rows from 2026-11-08 onward
  # are not static pages (Cloudflare Pages 20,000-file cap).
  added = p.get('added') or ''
  if added < '2026-11-08':
    return False
  if p.get('test') != 'listed':
    return False
  return 'Issue #' not in (p.get('note') or '')

def recent_verified(p):
  # recent curated rows (verified or metadata-listed) keep static pages; mirrors src/lib/ssg-plugins.js
  if later_bulk_listed(p):
    return False
  return p.get('test') in ('verified', 'listed') and (p.get('added') or '') >= '2026-10-14'

def ssg_en(p):
  if later_bulk_listed(p):
    return False
  slug = p.get('slug') or p['name']
  return (
    int(p.get('stars') or 0) >= 10
    or slug in en_i
    or (p.get('added') or '') < BULK
    or recent_verified(p)
  )

def ssg_zh(p):
  if later_bulk_listed(p):
    return False
  slug = p.get('slug') or p['name']
  has_zh = bool((p.get('desc_zh') or '').strip())
  return (
    slug in zh_i
    or ((p.get('added') or '') < BULK and has_zh)
    or recent_verified(p)
  )

out = {}
for cat, items in plugins.items():
  for p in items:
    if later_bulk_listed(p):
      continue
    if ssg_en(p) and ssg_zh(p):
      continue
    slug = p.get('slug') or p['name']
    out[slug] = {
      'slug': slug, 'name': p['name'], 'url': p.get('url') or '', 'pkg': p.get('pkg') or '',
      'npm': bool(p.get('npm') and p.get('pkg')), 'test': p.get('test') or 'listed',
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
