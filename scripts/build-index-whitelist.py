#!/usr/bin/env python3
"""Rebuild src/data/{gsc,bing}-whitelist.json and indexable-plugins.json.

Sources (override with env):
  GSC_JSON  default /workspace/seo-expert/raw3/dsh_gsc_pages90.json
  BING_JSON default /workspace/seo-expert/raw3/dsh_bing_clicked_urls.json

Matching normalizes www→apex and trailing slash. Core/non-plugin paths are kept
in the whitelist files but never affect the googlebot rule (that only runs on
plugin slug pages).
"""
import json, os
from urllib.parse import urlparse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
GSC = os.environ.get('GSC_JSON', '/workspace/seo-expert/raw3/dsh_gsc_pages90.json')
BING = os.environ.get('BING_JSON', '/workspace/seo-expert/raw3/dsh_bing_clicked_urls.json')
OUT = os.path.join(ROOT, 'src', 'data')

def norm_path(u: str) -> str:
    p = urlparse(u.strip())
    path = p.path or '/'
    if not path.endswith('/'):
        path += '/'
    return path

def load_bing(path):
    d = json.load(open(path, encoding='utf-8'))
    urls = d['urls'] if isinstance(d, dict) else d
    return {norm_path(u) for u in urls}

def load_gsc(path):
    d = json.load(open(path, encoding='utf-8'))
    # [[url, clicks, impressions], ...]
    return {norm_path(row[0]) for row in d}

bing = load_bing(BING)
gsc = load_gsc(GSC)
plugins = json.load(open(os.path.join(OUT, 'plugins.json'), encoding='utf-8'))
en, zh = set(), set()
n = 0
for items in plugins.values():
    for p in items:
        n += 1
        slug = p.get('slug') or p['name']
        stars = int(p.get('stars') or 0)
        en_path = f'/plugins/{slug}/'
        zh_path = f'/zh/plugins/{slug}/'
        # EN: stars OR either-lang GSC/Bing path (www/apex + slash already normalized)
        if stars >= 10 or en_path in gsc or en_path in bing or zh_path in gsc or zh_path in bing:
            en.add(slug)
        # ZH: only ZH-path signal (Bing whitelist /zh/plugins/* must stay indexable)
        if zh_path in bing or zh_path in gsc:
            zh.add(slug)

json.dump(sorted(gsc), open(os.path.join(OUT, 'gsc-whitelist.json'), 'w'), indent=1)
json.dump(sorted(bing), open(os.path.join(OUT, 'bing-whitelist.json'), 'w'), indent=1)
json.dump({
    'en': sorted(en),
    'zh': sorted(zh),
    'rules': {
        'en': 'stars>=10 OR /plugins/<slug>/ OR /zh/plugins/<slug>/ in gsc-whitelist OR bing-whitelist',
        'zh': '/zh/plugins/<slug>/ in bing-whitelist OR gsc-whitelist',
        'meta': 'non-indexable plugin pages: <meta name="googlebot" content="noindex, follow">',
        'core_pages': 'never noindexed by this rule (only plugin slug pages use it)',
    },
    'counts': {'en': len(en), 'zh': len(zh), 'total_plugins': n},
}, open(os.path.join(OUT, 'indexable-plugins.json'), 'w'), indent=1)
print(f'EN indexable {len(en)} / ZH {len(zh)} / total {n}; gsc paths {len(gsc)}; bing paths {len(bing)}')
