#!/usr/bin/env python3
"""用 GitHub REST API 补全插件的 license / updated / stars / language / archived。

合并 dsh.so 后，800+ 新插件的 license 为空、updated 为空、stars 是近似值。
这里对缺 license 或缺 updated 的插件，逐个查 /repos/{owner}/{repo}，回填：
  license   = license.spdx_id（缺则 license.name）
  updated   = pushed_at[:10]（真实最后推送日期）
  stars     = stargazers_count（仅当现有为 0/缺失时覆盖，不降级）
  forks     = forks_count（仅当现有为 0/缺失）
  language  = language（仅当为空）
  archived  = archived（权威）

用法：
  export GITHUB_TOKEN=xxx
  python -u scripts/enrich-github.py            # 处理所有缺 license/updated 的
  python -u scripts/enrich-github.py --limit 50 # 只处理前 50（调试）
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB = os.path.join(ROOT, 'src', 'data', 'plugins.json')

UA = {'User-Agent': 'dshbase-enrich', 'Accept': 'application/vnd.github+json'}


def gh(path):
    req = urllib.request.Request('https://api.github.com' + path, headers={
        'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'], **UA,
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                time.sleep(3 * (attempt + 1))
                continue
            raise
        except Exception:
            time.sleep(1)
    return None


def repo_of(p):
    return (p.get('url') or '').replace('https://github.com/', '').rstrip('/')


def enrich(p):
    repo = repo_of(p)
    if not repo:
        return False
    meta = gh(f'/repos/{repo}')
    if not meta or 'license' not in meta:
        return False
    changed = False
    lic = meta.get('license') or {}
    lic_name = lic.get('spdx_id') or lic.get('name') or ''
    if lic_name and not p.get('license'):
        p['license'] = lic_name
        changed = True
    pushed = (meta.get('pushed_at') or '')[:10]
    if pushed and not p.get('updated'):
        p['updated'] = pushed
        changed = True
    stars = meta.get('stargazers_count') or 0
    if stars and not (p.get('stars') or 0):
        p['stars'] = stars
        changed = True
    forks = meta.get('forks_count') or 0
    if forks and not (p.get('forks') or 0):
        p['forks'] = forks
        changed = True
    lang = meta.get('language') or ''
    if lang and not p.get('language'):
        p['language'] = lang
        changed = True
    if meta.get('archived'):
        p['archived'] = True
        changed = True
    return changed


def main():
    d = json.load(open(DB, encoding='utf-8'))
    allp = [p for items in d.values() for p in items]
    targets = [p for p in allp if not p.get('license') or not p.get('updated')]
    if '--limit' in sys.argv:
        targets = targets[:int(sys.argv[sys.argv.index('--limit') + 1])]
    print(f'需富化: {len(targets)} / 共 {len(allp)}')

    done = 0
    changed = 0
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(enrich, p): p for p in targets}
        for f in as_completed(futs):
            p = futs[f]
            try:
                if f.result():
                    changed += 1
            except Exception as e:
                print(f'  ! {p["name"]}: {e}')
            done += 1
            if done % 100 == 0:
                print(f'  {done}/{len(targets)} (changed {changed})')

    json.dump(d, open(DB, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\n完成：富化 {changed} 个，写回 {DB}')


if __name__ == '__main__':
    main()
