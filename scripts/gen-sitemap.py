#!/usr/bin/env python3
"""Generate sitemap-index + split sitemaps with lastmod.

- public/sitemap-index.xml  (robots.txt points here only)
  ├── sitemap-core.xml      static/core pages including /how-to/
  ├── sitemap-blog.xml
  └── sitemap-plugins-N.xml indexable plugin pages only (≤5000 each), EN+ZH
- public/sitemap-bing-full.xml  ALL plugin pages (EN+ZH). NOT in robots.txt;
  submit only in Bing Webmaster Tools.

Also writes a legacy public/sitemap.xml stub that 301-alternative points nothing
but keeps a redirect note; deploy keeps the old filename as a tiny index that
points at sitemap-index for safety. Actually: leave a short sitemap.xml that is
an index redirecting consumers — better write sitemap.xml as a copy of the index
so old GSC submissions still work, OR remove it. Brief: robots only → index.
We delete the giant single sitemap.xml and write the split set.
"""
import json, os, re, subprocess
from datetime import date, datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PUBLIC = os.path.join(ROOT, 'public')
SITE = 'https://dshbase.com'
TODAY = date.today().isoformat()
MAX = 5000

plugins = json.load(open(os.path.join(ROOT, 'src', 'data', 'plugins.json'), encoding='utf-8'))
indexable = json.load(open(os.path.join(ROOT, 'src', 'data', 'indexable-plugins.json'), encoding='utf-8'))
readmes = {}
try:
    readmes = json.load(open(os.path.join(ROOT, 'src', 'data', 'readmes.json'), encoding='utf-8'))
except Exception:
    pass
en_set, zh_set = set(indexable['en']), set(indexable['zh'])

def git_date(relpath):
    try:
        out = subprocess.check_output(
            ['git', 'log', '-1', '--format=%cs', '--', relpath],
            cwd=ROOT, stderr=subprocess.DEVNULL, text=True).strip()
        return out or TODAY
    except Exception:
        return TODAY

def plugin_lastmod(slug, p):
    r = readmes.get(slug) or {}
    for k in ('updatedAt', 'updated', 'fetchedAt'):
        v = r.get(k)
        if v:
            return str(v)[:10]
    added = (p.get('added') or '')[:10]
    return added or TODAY

STATIC = [
    ('/', 'weekly', '1.0', 'src/pages/index.astro'),
    ('/zh/', 'weekly', '0.9', 'src/pages/zh/index.astro'),
    ('/tutorial/', 'weekly', '0.9', 'src/pages/tutorial.astro'),
    ('/zh/tutorial/', 'weekly', '0.8', 'src/pages/zh/tutorial.astro'),
    ('/install/', 'monthly', '0.8', 'src/pages/install.astro'),
    ('/zh/install/', 'monthly', '0.8', 'src/pages/zh/install.astro'),
    ('/how-to/', 'monthly', '0.8', 'src/pages/how-to.astro'),
    ('/zh/how-to/', 'monthly', '0.8', 'src/pages/zh/how-to.astro'),
    ('/plugins/', 'weekly', '0.9', 'src/pages/plugins/index.astro'),
    ('/zh/plugins/', 'weekly', '0.9', 'src/pages/zh/plugins/index.astro'),
    ('/plugins/directory/', 'weekly', '0.9', 'src/pages/plugins/directory.astro'),
    ('/zh/plugins/directory/', 'weekly', '0.9', 'src/pages/zh/plugins/directory.astro'),
    ('/contributors/', 'weekly', '0.7', 'src/pages/contributors.astro'),
    ('/zh/contributors/', 'weekly', '0.7', 'src/pages/zh/contributors.astro'),
    ('/themes/', 'weekly', '0.7', 'src/pages/themes.astro'),
    ('/zh/themes/', 'weekly', '0.7', 'src/pages/zh/themes.astro'),
    ('/advanced-skins/', 'monthly', '0.6', 'src/pages/advanced-skins.astro'),
    ('/zh/advanced-skins/', 'monthly', '0.6', 'src/pages/zh/advanced-skins.astro'),
    ('/troubleshooting/', 'monthly', '0.7', 'src/pages/troubleshooting.astro'),
    ('/zh/troubleshooting/', 'monthly', '0.7', 'src/pages/zh/troubleshooting.astro'),
    ('/audit/', 'monthly', '0.7', 'src/pages/audit.astro'),
    ('/zh/audit/', 'monthly', '0.7', 'src/pages/zh/audit.astro'),
    ('/packs/', 'weekly', '0.85', 'src/pages/packs.astro'),
    ('/zh/packs/', 'weekly', '0.85', 'src/pages/zh/packs.astro'),
    ('/privacy/', 'yearly', '0.3', 'src/pages/privacy.astro'),
    ('/zh/privacy/', 'yearly', '0.3', 'src/pages/zh/privacy.astro'),
    ('/about/', 'yearly', '0.3', 'src/pages/about.astro'),
    ('/zh/about/', 'yearly', '0.3', 'src/pages/zh/about.astro'),
    ('/contact/', 'yearly', '0.3', 'src/pages/contact.astro'),
    ('/zh/contact/', 'yearly', '0.3', 'src/pages/zh/contact.astro'),
    ('/blog/', 'weekly', '0.8', 'src/pages/blog/index.astro'),
    ('/zh/blog/', 'weekly', '0.8', 'src/pages/zh/blog/index.astro'),
]

def write_urlset(path, entries):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod, freq, pri in entries:
        lines.append(
            f'  <url><loc>{SITE}{loc}</loc><lastmod>{lastmod}</lastmod>'
            f'<changefreq>{freq}</changefreq><priority>{pri}</priority></url>'
        )
    lines.append('</urlset>\n')
    open(path, 'w', encoding='utf-8').write('\n'.join(lines))
    return len(entries)

core = []
for loc, freq, pri, src in STATIC:
    core.append((loc, git_date(src), freq, pri))

# directory pagination pages (filled after we know page count — stub via glob later)
# Will be appended by scanning dist is too late; encode known pattern from PAGE_SIZE.
PAGE_SIZE = 100
all_slugs = []
for items in plugins.values():
    for p in items:
        all_slugs.append(p.get('slug') or p['name'])
# sort for stable pagination (stars desc then name) — must match directory pages
flat = []
for cat, items in plugins.items():
    for p in items:
        flat.append(p)
flat.sort(key=lambda p: (-int(p.get('stars') or 0), (p.get('slug') or p['name'])))
n_pages = max(1, (len(flat) + PAGE_SIZE - 1) // PAGE_SIZE)
for n in range(1, n_pages + 1):
    core.append((f'/plugins/directory/page/{n}/', TODAY, 'weekly', '0.7'))
    core.append((f'/zh/plugins/directory/page/{n}/', TODAY, 'weekly', '0.7'))

blog = []
blog_dir = os.path.join(ROOT, 'src', 'pages', 'blog')
for f in sorted(os.listdir(blog_dir)):
    if not f.endswith('.astro') or f == 'index.astro':
        continue
    slug = f[:-6]
    lm = git_date(f'src/pages/blog/{f}')
    blog.append((f'/blog/{slug}/', lm, 'monthly', '0.6'))
    blog.append((f'/zh/blog/{slug}/', lm, 'monthly', '0.6'))

idx_plugins = []
all_plugins = []
for p in flat:
    slug = p.get('slug') or p['name']
    lm = plugin_lastmod(slug, p)
    en = (f'/plugins/{slug}/', lm, 'monthly', '0.6')
    zh = (f'/zh/plugins/{slug}/', lm, 'monthly', '0.5')
    all_plugins.extend([en, zh])
    if slug in en_set:
        idx_plugins.append(en)
    if slug in zh_set:
        idx_plugins.append(zh)

# write pieces
n_core = write_urlset(os.path.join(PUBLIC, 'sitemap-core.xml'), core)
n_blog = write_urlset(os.path.join(PUBLIC, 'sitemap-blog.xml'), blog)

plugin_files = []
for i in range(0, len(idx_plugins), MAX):
    chunk = idx_plugins[i:i + MAX]
    name = f'sitemap-plugins-{i // MAX}.xml'
    write_urlset(os.path.join(PUBLIC, name), chunk)
    plugin_files.append(name)

n_bing = write_urlset(os.path.join(PUBLIC, 'sitemap-bing-full.xml'), all_plugins)

# index (Google / robots)
index_children = ['sitemap-core.xml', 'sitemap-blog.xml'] + plugin_files
lines = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for name in index_children:
    lines.append(f'  <sitemap><loc>{SITE}/{name}</loc><lastmod>{TODAY}</lastmod></sitemap>')
lines.append('</sitemapindex>\n')
open(os.path.join(PUBLIC, 'sitemap-index.xml'), 'w', encoding='utf-8').write('\n'.join(lines))

# Remove legacy giant sitemap.xml so it is not served; write a tiny pointer index
# matching sitemap-index so old /sitemap.xml submissions still resolve.
open(os.path.join(PUBLIC, 'sitemap.xml'), 'w', encoding='utf-8').write('\n'.join(lines))

print(f'sitemap-index: core={n_core} blog={n_blog} plugins_indexable={len(idx_plugins)} in {len(plugin_files)} files; bing_full={n_bing}; dir_pages={n_pages}')
