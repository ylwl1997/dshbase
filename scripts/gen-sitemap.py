#!/usr/bin/env python3
"""生成完整 sitemap.xml（保留静态页优先级 + 补全插件/博客页）。"""
import json
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB = os.path.join(ROOT, 'src', 'data', 'plugins.json')
BLOG_DIR = os.path.join(ROOT, 'src', 'pages', 'blog')
OUT = os.path.join(ROOT, 'public', 'sitemap.xml')
SITE = 'https://dshbase.com'

# 静态页（保留原优先级，不影响 GSC）
STATIC = [
    ('/', 'weekly', '1.0'),
    ('/zh/', 'weekly', '0.9'),
    ('/tutorial/', 'weekly', '0.9'),
    ('/zh/tutorial/', 'weekly', '0.8'),
    ('/install/', 'monthly', '0.8'),
    ('/zh/install/', 'monthly', '0.8'),
    ('/plugins/', 'weekly', '0.9'),
    ('/zh/plugins/', 'weekly', '0.9'),
    ('/plugins/directory/', 'weekly', '0.9'),
    ('/zh/plugins/directory/', 'weekly', '0.9'),
    ('/themes/', 'weekly', '0.7'),
    ('/zh/themes/', 'weekly', '0.7'),
    ('/advanced-skins/', 'monthly', '0.6'),
    ('/zh/advanced-skins/', 'monthly', '0.6'),
    ('/troubleshooting/', 'monthly', '0.7'),
    ('/zh/troubleshooting/', 'monthly', '0.7'),
    ('/audit/', 'monthly', '0.7'),
    ('/zh/audit/', 'monthly', '0.7'),
    ('/privacy/', 'yearly', '0.3'),
    ('/zh/privacy/', 'yearly', '0.3'),
    ('/about/', 'yearly', '0.3'),
    ('/zh/about/', 'yearly', '0.3'),
    ('/contact/', 'yearly', '0.3'),
    ('/zh/contact/', 'yearly', '0.3'),
    ('/blog/', 'weekly', '0.8'),
    ('/zh/blog/', 'weekly', '0.8'),
]

urls = list(STATIC)

# 插件详情页
d = json.load(open(DB, encoding='utf-8'))
for items in d.values():
    for p in items:
        slug = p.get('slug') or p['name']
        urls.append((f'/plugins/{slug}/', 'monthly', '0.6'))
        urls.append((f'/zh/plugins/{slug}/', 'monthly', '0.6'))

# 博客文章
for f in os.listdir(BLOG_DIR):
    if not f.endswith('.astro') or f == 'index.astro':
        continue
    slug = f[:-6]
    urls.append((f'/blog/{slug}/', 'monthly', '0.6'))
    urls.append((f'/zh/blog/{slug}/', 'monthly', '0.6'))

# 去重保序
seen = set()
unique = []
for u, freq, pri in urls:
    if u not in seen:
        seen.add(u)
        unique.append((u, freq, pri))

lines = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for u, freq, pri in unique:
    lines.append(f'  <url><loc>{SITE}{u}</loc><changefreq>{freq}</changefreq><priority>{pri}</priority></url>')
lines.append('</urlset>')

open(OUT, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
print(f'sitemap.xml: {len(unique)} 个 URL -> {OUT}')
