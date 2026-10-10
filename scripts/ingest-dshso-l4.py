#!/usr/bin/env python3
"""Ingest dsh.so L4+ plugins into dshbase as Verified.

Private data source only — public site copy must never mention dsh.so.
Dedup by github owner/repo (case-insensitive) and npm package name.
Usage:
  python scripts/ingest-dshso-l4.py [--dry-run] [--cache-dir /tmp/dshso-cache]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB = os.path.join(ROOT, 'src', 'data', 'plugins.json')
SYNC = os.path.join(ROOT, 'src', 'data', 'sync-date.json')
UA = {'User-Agent': 'dshbase-catalog-bot/1.0'}

PLUGINS_INDEX = 'https://www.dsh.so/plugins-index.json'
SEARCH_INDEX = 'https://www.dsh.so/search-index.json'

CAT_MERGE = {
    'Developer': ['Developer'],
    'AI Models': ['AI Models'],
    'UI & Skins': ['UI & Skins', 'Game'],
    'Knowledge': ['Knowledge'],
    'Desktop': ['Desktop', 'Launcher'],
    'Automation': ['Automation'],
    'Network': ['Network'],
    'Browser': ['Browser'],
    'Terminal': ['Terminal'],
    'Storage': ['Storage'],
    'Vision': ['Vision'],
    'Data': ['Data', 'Finance'],
    'Security': ['Security'],
    'Productivity': ['Productivity'],
    'Content': ['Content', 'Media'],
}
THEIR_CAT_TO_NEW = {s: new for new, srcs in CAT_MERGE.items() for s in srcs}
USE_CASES = {
    'Terminal / Shell', 'File', 'Vision / OCR', 'Memory', 'Database',
    'Web search', 'Storage', 'GitHub integration', 'Code review', 'Notifications',
}


def http_get_json(url: str, timeout=120):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', errors='replace'))


def parse_stars(v) -> int:
    if v is None:
        return 0
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip().lower().replace(',', '')
    m = re.match(r'([\d.]+)\s*([km]?)', s)
    if not m:
        return 0
    n = float(m.group(1))
    u = m.group(2)
    if u == 'k':
        n *= 1000
    elif u == 'm':
        n *= 1_000_000
    return int(n)


def norm_repo(owner: str, repo: str) -> str:
    return f"{owner.strip()}/{repo.strip().removesuffix('.git')}".lower()


def repo_from_github_url(url: str | None) -> str | None:
    m = re.search(r'github\.com/([^/\s]+)/([^/\s#?]+)', url or '', re.I)
    return norm_repo(m.group(1), m.group(2)) if m else None


def repo_from_install(inst: str | None) -> str | None:
    m = re.search(r'add\s+github:([^/\s#]+)/([^/\s#]+)', inst or '', re.I)
    return norm_repo(m.group(1), m.group(2)) if m else None


def npm_from_install(inst: str | None) -> tuple[str | None, str]:
    """Return (package, version) from `dsh plugin add …`."""
    m = re.search(r'dsh plugin(?:\s+--profile\s+\w+)?\s+add\s+(\S+)', inst or '')
    if not m:
        return None, ''
    t = m.group(1)
    if t.startswith('github:'):
        return None, ''
    if t.startswith('@'):
        m2 = re.match(r'(@[^/]+/[^@]+)(?:@(.+))?$', t)
        if m2:
            return m2.group(1), m2.group(2) or ''
        return t, ''
    m2 = re.match(r'([^@]+)(?:@(.+))?$', t)
    if m2:
        return m2.group(1), m2.group(2) or ''
    return t, ''


def is_l4_plus(p: dict) -> bool:
    v = p.get('verification') or {}
    lv = v.get('level')
    return isinstance(lv, int) and lv >= 4


def primary_cat(cats: list[str]) -> str:
    for c in cats:
        mapped = THEIR_CAT_TO_NEW.get(c)
        if mapped:
            return mapped
    return 'Developer'


def load_indexes(cache_dir: str):
    os.makedirs(cache_dir, exist_ok=True)
    pi_path = os.path.join(cache_dir, 'plugins-index.json')
    si_path = os.path.join(cache_dir, 'search-index.json')
    if not os.path.exists(pi_path):
        print('fetch plugins-index…')
        json.dump(http_get_json(PLUGINS_INDEX), open(pi_path, 'w'), ensure_ascii=False)
    if not os.path.exists(si_path):
        print('fetch search-index…')
        json.dump(http_get_json(SEARCH_INDEX), open(si_path, 'w'), ensure_ascii=False)
    # Prefer fresher /tmp copies if present and larger
    for src, dst in (('/tmp/dsh-plugins-index.json', pi_path), ('/tmp/dsh-search-index.json', si_path)):
        if os.path.exists(src) and os.path.getsize(src) >= os.path.getsize(dst):
            os.replace(src, dst) if False else None
            # copy if tmp newer
            if os.path.getmtime(src) >= os.path.getmtime(dst) - 1:
                import shutil
                shutil.copy2(src, dst)
    pi = json.load(open(pi_path, encoding='utf-8'))
    si = json.load(open(si_path, encoding='utf-8'))
    return pi, si


def npm_repo_lookup(pkg: str) -> str | None:
    try:
        url = 'https://registry.npmjs.org/' + pkg.replace('/', '%2F')
        req = urllib.request.Request(url, headers={**UA, 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read().decode())
        repo = d.get('repository')
        if isinstance(repo, dict):
            repo = repo.get('url') or ''
        if isinstance(repo, str):
            repo = repo.replace('git+', '').replace('git://', 'https://').replace('ssh://git@', 'https://')
            repo = re.sub(r'^github:', 'https://github.com/', repo)
            return repo_from_github_url(repo)
    except Exception:
        return None
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--cache-dir', default='/tmp/dshso-cache')
    ap.add_argument('--npm-lookup', action='store_true', help='Resolve missing github via npm registry')
    args = ap.parse_args()

    pi, si = load_indexes(args.cache_dir)
    plugins = pi['plugins'] if isinstance(pi, dict) else pi
    l4 = [p for p in plugins if is_l4_plus(p)]
    print(f'index plugins={len(plugins)} L4+={len(l4)}')

    by_slug = {x['slug']: x for x in si if x.get('slug')}
    by_name: dict[str, list] = defaultdict(list)
    for x in si:
        by_name[str(x.get('name') or '').lower()].append(x)

    our = json.load(open(DB, encoding='utf-8'))
    # ensure all cats exist
    for c in CAT_MERGE:
        our.setdefault(c, [])

    by_repo: dict[str, tuple[str, dict]] = {}
    by_pkg: dict[str, tuple[str, dict]] = {}
    for cat, items in our.items():
        for p in items:
            r = repo_from_github_url(p.get('url'))
            if r:
                by_repo.setdefault(r, (cat, p))
            pkg = (p.get('pkg') or '').lower()
            if pkg:
                by_pkg.setdefault(pkg, (cat, p))

    today = date.today().isoformat()
    stats = {'new': 0, 'merged': 0, 'skip_dup': 0, 'skip_no_id': 0, 'seen_keys': set()}

    # Precompute identities
    pending_npm: list[tuple[dict, str, str]] = []  # (p, pkg, ver) needing repo

    rows = []
    for p in l4:
        repo = repo_from_github_url(p.get('source')) or repo_from_install(p.get('install'))
        pkg, ver = npm_from_install(p.get('install'))
        # search-index fallback
        si_hit = None
        if not repo:
            for key in (p.get('id'), p.get('name')):
                if not key:
                    continue
                si_hit = by_slug.get(key)
                if not si_hit:
                    hits = by_name.get(str(key).lower()) or []
                    si_hit = hits[0] if hits else None
                if si_hit and si_hit.get('owner') and si_hit.get('repo'):
                    repo = norm_repo(si_hit['owner'], si_hit['repo'])
                    break
        if not repo and pkg:
            pending_npm.append((p, pkg, ver))
            continue
        if not repo and not pkg:
            stats['skip_no_id'] += 1
            continue
        rows.append((p, repo, pkg, ver, si_hit))

    if pending_npm and args.npm_lookup:
        print(f'npm registry lookup for {len(pending_npm)}…')
        def one(item):
            p, pkg, ver = item
            return p, pkg, ver, npm_repo_lookup(pkg)
        with ThreadPoolExecutor(max_workers=20) as ex:
            for p, pkg, ver, repo in ex.map(lambda it: one(it), pending_npm):
                if repo or pkg:
                    rows.append((p, repo, pkg, ver, None))
                else:
                    stats['skip_no_id'] += 1
    else:
        # without npm lookup: still keep npm-only with synthetic github from alias owner if possible
        for p, pkg, ver in pending_npm:
            alias = p.get('alias') or ''
            m = re.match(r'@([^/]+)/(.+)$', alias)
            # Don't invent github from npm scope — skip
            if pkg:
                # store with empty repo → skip later unless we set url to npm
                stats['skip_no_id'] += 1
            else:
                stats['skip_no_id'] += 1

    print(f'resolved rows={len(rows)} skip_no_id={stats["skip_no_id"]}')

    for p, repo, pkg, ver, si_hit in rows:
        # dedupe within this ingest batch
        key = repo or f'pkg:{(pkg or "").lower()}'
        if key in stats['seen_keys']:
            stats['skip_dup'] += 1
            continue
        stats['seen_keys'].add(key)

        existing = None
        cat = None
        if repo and repo in by_repo:
            cat, existing = by_repo[repo]
        elif pkg and pkg.lower() in by_pkg:
            cat, existing = by_pkg[pkg.lower()]

        # meta from search-index
        if not si_hit:
            for key2 in (p.get('id'), p.get('name')):
                if not key2:
                    continue
                si_hit = by_slug.get(key2) or (by_name.get(str(key2).lower()) or [None])[0]
                if si_hit:
                    break
        cats = (si_hit or {}).get('cats') or []
        new_cat = primary_cat(cats)
        desc = (p.get('description') or (si_hit or {}).get('description') or '').strip()
        stars = parse_stars(p.get('stars') if p.get('stars') is not None else (si_hit or {}).get('starsN') or (si_hit or {}).get('stars'))
        ucs = [u for u in ((si_hit or {}).get('ucs') or []) if u in USE_CASES]
        trust = (si_hit or {}).get('trust') or 'Unrated'
        name = p.get('name') or (si_hit or {}).get('name') or (pkg.split('/')[-1] if pkg else 'plugin')
        url = f'https://github.com/{repo}' if repo else ''

        if existing:
            # merge update — never duplicate
            existing['test'] = 'verified'
            existing['testDate'] = today
            if stars and stars > (existing.get('stars') or 0):
                existing['stars'] = stars
            if desc:
                if not (existing.get('desc_en') or '').strip():
                    existing['desc_en'] = desc
                if not (existing.get('desc') or '').strip():
                    existing['desc'] = desc
            if pkg and not existing.get('pkg'):
                existing['pkg'] = pkg
                existing['npm'] = True
            if ver and not existing.get('ver'):
                existing['ver'] = ver
            if ucs and not existing.get('ucs'):
                existing['ucs'] = ucs
            if trust and existing.get('trust') in (None, '', 'Unrated'):
                existing['trust'] = trust
            if url and 'github.com' not in (existing.get('url') or ''):
                existing['url'] = url
            existing.pop('webonly', None)
            note = existing.get('note') or ''
            if note.startswith('验证:') or '；验证:' in note:
                existing.pop('note', None)
            stats['merged'] += 1
            stats['skip_dup'] += 0  # merged is update, not skip
            # refresh indexes if pkg newly set
            if pkg:
                by_pkg[pkg.lower()] = (cat, existing)
            continue

        # brand-new entry
        entry = {
            'name': name,
            'url': url,
            'pkg': pkg or '',
            'ver': ver or '',
            'npm': bool(pkg),
            'test': 'verified',
            'testDate': today,
            'desc': desc,
            'desc_en': desc,
            'desc_zh': '',
            'stars': stars,
            'forks': 0,
            'issues': 0,
            'language': '',
            'updated': '',
            'archived': ((si_hit or {}).get('health') == 'Archived'),
            'added': today,
            'license': '',
            'ucs': ucs,
            'trust': trust,
        }
        if not entry['url']:
            stats['skip_no_id'] += 1
            continue
        our[new_cat].append(entry)
        if repo:
            by_repo[repo] = (new_cat, entry)
        if pkg:
            by_pkg[pkg.lower()] = (new_cat, entry)
        stats['new'] += 1

    total = sum(len(v) for v in our.values())
    print(f"NEW={stats['new']} MERGED={stats['merged']} SKIP_DUP_BATCH={stats['skip_dup']} SKIP_NO_ID={stats['skip_no_id']} TOTAL={total}")

    if args.dry_run:
        print('[dry-run] not writing')
        return

    json.dump(our, open(DB, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump({'updated': today}, open(SYNC, 'w', encoding='utf-8'), indent=1)
    print(f'wrote {DB}')

    # assign slugs
    import subprocess
    subprocess.check_call([sys.executable, os.path.join(ROOT, 'scripts', 'assign-slugs.py')], cwd=ROOT)


if __name__ == '__main__':
    main()
