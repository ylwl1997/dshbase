#!/usr/bin/env python3
"""Generate sitemap-index + split sitemaps with lastmod.

- public/sitemap-index.xml  (robots.txt points here only)
  ├── sitemap-core.xml      static/core pages (no privacy; no thin directory pagination)
  ├── sitemap-blog.xml
  └── sitemap-plugins-N.xml all live plugin detail pages (≤5000 each), EN+ZH
- public/sitemap-bing-full.xml  ALL live plugin pages (EN+ZH). NOT in robots.txt;
  submit only in Bing Webmaster Tools.

Plugin URLs that 301 via public/_redirects (e.g. /plugins/flowix/ → directory)
are omitted from every sitemap — Ahrefs/GSC must not see redirecting locs.

Also writes public/sitemap.xml as a copy of the index so old submissions still resolve.
"""
import json, os, re, subprocess
from datetime import date

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PUBLIC = os.path.join(ROOT, 'public')
SITE = 'https://dshbase.com'
TODAY = date.today().isoformat()
MAX = 5000

plugins = json.load(open(os.path.join(ROOT, 'src', 'data', 'plugins.json'), encoding='utf-8'))
readmes = {}
try:
    readmes = json.load(open(os.path.join(ROOT, 'src', 'data', 'readmes.json'), encoding='utf-8'))
except Exception:
    pass

def load_redirected_plugin_slugs():
    """Slugs with a 301 away from /plugins/<slug>/ (or zh twin) in public/_redirects."""
    path = os.path.join(PUBLIC, '_redirects')
    slugs = set()
    if not os.path.isfile(path):
        return slugs
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split()
        if len(parts) < 3 or parts[2] not in ('301', '302'):
            continue
        m = re.match(r'^/(?:zh/)?plugins/([^/]+)/$', parts[0])
        if m:
            slugs.add(m.group(1))
    return slugs

REDIRECTED = load_redirected_plugin_slugs()

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

# Privacy is noindex; directory pagination (/page/N/) is thin/noindex — omit both.
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
    ('/plugins/directory/', 'weekly', '0.9', 'src/pages/plugins/directory/index.astro'),
    ('/zh/plugins/directory/', 'weekly', '0.9', 'src/pages/zh/plugins/directory/index.astro'),
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
    # directory.astro path historically differed; fall back to TODAY via git_date
    core.append((loc, git_date(src), freq, pri))

flat = []
for cat, items in plugins.items():
    for p in items:
        flat.append(p)
flat.sort(key=lambda p: (-int(p.get('stars') or 0), (p.get('slug') or p['name'])))

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
skipped = 0
for p in flat:
    slug = p.get('slug') or p['name']
    if slug in REDIRECTED:
        skipped += 1
        continue
    lm = plugin_lastmod(slug, p)
    en = (f'/plugins/{slug}/', lm, 'monthly', '0.6')
    zh = (f'/zh/plugins/{slug}/', lm, 'monthly', '0.5')
    all_plugins.extend([en, zh])
    # All live plugin detail pages are indexable again (EN + ZH).
    idx_plugins.extend([en, zh])

# write pieces
n_core = write_urlset(os.path.join(PUBLIC, 'sitemap-core.xml'), core)
n_blog = write_urlset(os.path.join(PUBLIC, 'sitemap-blog.xml'), blog)

# Remove stale plugin sitemap shards from prior runs (count can shrink/grow).
for name in os.listdir(PUBLIC):
    if re.match(r'^sitemap-plugins-\d+\.xml$', name):
        os.remove(os.path.join(PUBLIC, name))

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
open(os.path.join(PUBLIC, 'sitemap.xml'), 'w', encoding='utf-8').write('\n'.join(lines))

print(
    f'sitemap-index: core={n_core} blog={n_blog} plugins_indexable={len(idx_plugins)} '
    f'in {len(plugin_files)} files; bing_full={n_bing}; redirected_skipped={skipped} '
    f'(slugs={len(REDIRECTED)})'
)
assert 'flowix' in REDIRECTED, 'flowix must be excluded via _redirects'


# Keep Pages Function fallback map in sync for non-SSG plugin slugs (CF 20k file cap).
import subprocess, sys
try:
    subprocess.check_call([sys.executable, os.path.join(os.path.dirname(__file__), 'gen-plugin-fallback.py')])
except Exception as e:
    print('gen-plugin-fallback skipped:', e)

