#!/usr/bin/env python3
"""深查「有 dsh-plugin topic 但 name/描述/URL 无 DSH 信号」的候选插件，
用 DSH 专属标记（cordis.patch.yml / dsh.bundle / package.json dsh 字段）区分真 DSH 与蹭标签。

用法: GITHUB_TOKEN=xxx python scripts/verify-tag-squatters.py [--workers N]
结果写 audit-tagsquat.txt + audit-tagsquat-keep.txt
"""
import base64
import json
import os
import re
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

DATA = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'data', 'plugins.json'))
SUSPECT_OUT = os.path.join(os.path.dirname(__file__), '..', 'audit-tagsquat.txt')
KEEP_OUT = os.path.join(os.path.dirname(__file__), '..', 'audit-tagsquat-keep.txt')

TOKEN = os.environ.get('GITHUB_TOKEN', '')
SIG = re.compile(r'deepseek|harness|cordis|dsh', re.I)
STRONG = ('cordis.patch.yml', 'cordis.yml', 'dsh.bundle', 'dsh.bundle.yml', 'dsh.bundle.patch')

_lock = threading.Lock()
_done = 0
_total = 0


def gh(path):
    req = urllib.request.Request('https://api.github.com' + path, headers={
        'Authorization': 'Bearer ' + TOKEN,
        'User-Agent': 'dshbase-verify',
        'Accept': 'application/vnd.github+json',
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def fetch(key):
    global _done
    for attempt in range(3):
        try:
            items = gh(f'/repos/{key}/contents/')
            root = [f.get('name', '') for f in items] if isinstance(items, list) else []
            strong = any(b in root for b in STRONG)
            has_skill = 'SKILL.md' in root
            dsh_field = False
            if not strong:
                pkg = gh(f'/repos/{key}/contents/package.json')
                if isinstance(pkg, dict) and pkg.get('content'):
                    try:
                        pj = json.loads(base64.b64decode(pkg['content']).decode('utf-8'))
                        dsh_field = bool(pj.get('dsh'))
                    except Exception:
                        pass
            with _lock:
                _done += 1
                print(f'[{_done}/{_total}] {key}', flush=True)
            return {'root': root, 'strong': strong, 'has_skill': has_skill, 'dsh_field': dsh_field, 'status': 'ok'}
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                time.sleep(60); continue
            return {'status': f'http{e.code}'}
        except Exception as e:
            if attempt == 2:
                return {'status': 'err', 'err': str(e)}
            time.sleep(2 * (attempt + 1))
    return {'status': 'err'}


def main():
    global _total
    d = json.load(open(DATA, encoding='utf-8'))
    cand = []
    for cat, items in d.items():
        for p in items:
            name = p.get('name') or ''
            text = name + ' ' + (p.get('desc_en') or '') + ' ' + (p.get('desc_zh') or '') + ' ' + (p.get('url') or '')
            if not SIG.search(text):
                m = re.search(r'github\.com/([^/]+/[^/]+?)/?$', p.get('url') or '')
                if m:
                    cand.append((cat, name, m.group(1).rstrip('.git').lower(), p.get('stars', 0)))

    _total = len(cand)
    print(f'候选 {len(cand)} 个，深查 DSH 专属标记...', flush=True)

    workers = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 6
    rows = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fetch, c[2]): c for c in cand}
        for fut in as_completed(futs):
            cat, name, key, stars = futs[fut]
            try:
                meta = fut.result()
            except Exception as e:
                meta = {'status': 'err', 'err': str(e)}
            rows.append((cat, name, key, stars, meta))

    suspects = []
    keeps = []
    for cat, name, key, stars, meta in rows:
        if meta.get('status') != 'ok':
            # 仓库又 404/出错，归入待删
            suspects.append((cat, name, key, stars, meta.get('status', '?')))
            continue
        if meta.get('strong') or meta.get('dsh_field'):
            keeps.append((cat, name, key, stars, 'bundle/dsh字段'))
        elif meta.get('has_skill'):
            keeps.append((cat, name, key, stars, '仅SKILL.md(需人工)'))
        else:
            suspects.append((cat, name, key, stars, '无DSH标记'))

    suspects.sort(key=lambda x: -x[3])
    keeps.sort(key=lambda x: -x[3])
    print(f'\n===== 结果 =====', flush=True)
    print(f'  确认蹭标签/非DSH: {len(suspects)}', flush=True)
    print(f'  保留(有DSH标记/仅SKILL.md): {len(keeps)}', flush=True)

    with open(SUSPECT_OUT, 'w', encoding='utf-8') as f:
        for cat, name, key, stars, why in suspects:
            f.write(f'{name}\t{key}\t{cat}\t★{stars}\t{why}\n')
    with open(KEEP_OUT, 'w', encoding='utf-8') as f:
        for cat, name, key, stars, why in keeps:
            f.write(f'{name}\t{key}\t{cat}\t★{stars}\t{why}\n')

    print('\n--- 待删（蹭标签/非DSH）---', flush=True)
    for cat, name, key, stars, why in suspects:
        print(f'  ★{stars:6} {name:34} {key}  [{why}]', flush=True)
    print('\n--- 保留 ---', flush=True)
    for cat, name, key, stars, why in keeps:
        print(f'  ★{stars:6} {name:34} {key}  [{why}]', flush=True)


if __name__ == '__main__':
    main()
