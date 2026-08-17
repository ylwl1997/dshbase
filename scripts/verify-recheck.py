#!/usr/bin/env python3
"""重验 78 个「http404」候选（疑似二级限流误判），低速 + 限流感知。
对每个仓库: 先 /repos/{key} 确认存活，再 /contents/ 查 DSH 专属标记。
分类: keep(bundle/dsh字段) / keep_skill(仅SKILL.md) / drop(无DSH标记) / gone(真404)
结果写 audit-tagsquat-recheck.txt
"""
import base64
import json
import os
import re
import sys
import time
import urllib.request

TOKEN = os.environ.get('GITHUB_TOKEN', '')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TXT = os.path.join(ROOT, 'audit-tagsquat.txt')
OUT = os.path.join(ROOT, 'audit-tagsquat-recheck.txt')
STRONG = ('cordis.patch.yml', 'cordis.yml', 'dsh.bundle', 'dsh.bundle.yml', 'dsh.bundle.patch')


def gh(path):
    req = urllib.request.Request('https://api.github.com' + path, headers={
        'Authorization': 'Bearer ' + TOKEN,
        'User-Agent': 'dshbase-recheck',
        'Accept': 'application/vnd.github+json',
    })
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.status, dict(r.headers), json.loads(r.read())


def get(path):
    for attempt in range(6):
        try:
            st, hdrs, data = gh(path)
            rem = int(hdrs.get('X-RateLimit-Remaining', '5000'))
            if st == 200:
                return 'ok', data, rem
            if st in (403, 429):
                print(f'  限流({st}) 剩余{rem}，等 70s...', flush=True)
                time.sleep(70)
                continue
            return f'http{st}', None, rem
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                print(f'  限流({e.code})，等 70s...', flush=True)
                time.sleep(70)
                continue
            if e.code == 404:
                return 'http404', None, int(dict(e.headers).get('X-RateLimit-Remaining', '5000'))
            if attempt == 5:
                return f'http{e.code}', None, 0
            time.sleep(3 * (attempt + 1))
        except Exception as e:
            if attempt == 5:
                return 'err', str(e), 0
            time.sleep(3 * (attempt + 1))
    return 'err', None, 0


def main():
    repos = []
    for line in open(TXT, encoding='utf-8'):
        line = line.rstrip('\n')
        if '\thttp404\t' in line or line.endswith('\thttp404'):
            parts = line.split('\t')
            repos.append((parts[0], parts[1], parts[2], parts[3]))  # name, key, cat, stars
    print(f'重验 {len(repos)} 个 http404 候选...', flush=True)

    keep, drop, gone, err = [], [], [], []
    for i, (name, key, cat, stars) in enumerate(repos, 1):
        st, data, rem = get(f'/repos/{key}')
        if st == 'http404':
            # 再确认一次 repo 端点（排除 contents 限流误判）
            st2, data2, rem2 = get(f'/repos/{key}')
            if st2 == 'http404':
                gone.append((name, key, cat, stars))
                print(f'[{i}/{len(repos)}] GONE {key}', flush=True)
                continue
            st, data, rem = st2, data2, rem2
        if st != 'ok':
            err.append((name, key, cat, stars, st))
            print(f'[{i}/{len(repos)}] ERR {key} ({st})', flush=True)
            continue
        # 查 contents
        stc, items, remc = get(f'/repos/{key}/contents/')
        if stc != 'ok':
            err.append((name, key, cat, stars, f'contents:{stc}'))
            print(f'[{i}/{len(repos)}] ERR-CONTENTS {key} ({stc})', flush=True)
            continue
        root = [f.get('name', '') for f in items] if isinstance(items, list) else []
        strong = any(b in root for b in STRONG)
        has_skill = 'SKILL.md' in root
        dsh_field = False
        if not strong:
            stp, pkg, _ = get(f'/repos/{key}/contents/package.json')
            if stp == 'ok' and isinstance(pkg, dict) and pkg.get('content'):
                try:
                    pj = json.loads(base64.b64decode(pkg['content']).decode('utf-8'))
                    dsh_field = bool(pj.get('dsh'))
                except Exception:
                    pass
        if strong or dsh_field:
            keep.append((name, key, cat, stars, 'bundle/dsh字段'))
        elif has_skill:
            keep.append((name, key, cat, stars, '仅SKILL.md'))
        else:
            drop.append((name, key, cat, stars, '无DSH标记'))
        time.sleep(0.4)  # 温和限速

    print(f'\n===== 重验结果 =====', flush=True)
    print(f'  drop(无DSH标记): {len(drop)}', flush=True)
    print(f'  keep(有DSH标记): {len(keep)}', flush=True)
    print(f'  gone(真404): {len(gone)}', flush=True)
    print(f'  err(待人工): {len(err)}', flush=True)

    with open(OUT, 'w', encoding='utf-8') as f:
        for name, key, cat, stars, why in drop:
            f.write(f'DROP\t{name}\t{key}\t{cat}\t{stars}\t{why}\n')
        for name, key, cat, stars, why in keep:
            f.write(f'KEEP\t{name}\t{key}\t{cat}\t{stars}\t{why}\n')
        for name, key, cat, stars in gone:
            f.write(f'GONE\t{name}\t{key}\t{cat}\t{stars}\n')
        for name, key, cat, stars, why in err:
            f.write(f'ERR\t{name}\t{key}\t{cat}\t{stars}\t{why}\n')

    print('\n--- DROP ---', flush=True)
    for n, k, c, s, w in sorted(drop, key=lambda x: -int(x[3].lstrip('★'))):
        print(f'  {s:8} {n:32} {k}  [{w}]', flush=True)
    print('\n--- KEEP ---', flush=True)
    for n, k, c, s, w in sorted(keep, key=lambda x: -int(x[3].lstrip('★'))):
        print(f'  {s:8} {n:32} {k}  [{w}]', flush=True)
    print('\n--- GONE ---', flush=True)
    for n, k, c, s in gone:
        print(f'  {s:8} {n:32} {k}', flush=True)
    print('\n--- ERR ---', flush=True)
    for n, k, c, s, w in err:
        print(f'  {s:8} {n:32} {k}  [{w}]', flush=True)


if __name__ == '__main__':
    main()
