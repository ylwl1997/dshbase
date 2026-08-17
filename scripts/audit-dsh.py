#!/usr/bin/env python3
"""审计 plugins.json：拉取每个仓库的 topics/description，找出非 DeepSeek Harness 生态插件。

分类：
  dsh          有 dsh-plugin / deepseek-harness topic（明确 DSH 生态）
  dsh-desc     无 DSH topic，但 name/desc 含 deepseek / cordis（大概率 DSH 相关）
  harness-only 无 DSH topic，仅含 harness（弱信号，需人工看）
  suspect      以上皆无 —— 疑似非 DSH 生态
  gone         仓库 404（已改名/删除）

用法: GITHUB_TOKEN=xxx python scripts/audit-dsh.py [--workers N]
结果写 audit-report.json + audit-suspects.txt，缓存 audit-repos.cache.json 断点续跑（每 100 条落盘）。
"""
import json
import os
import re
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

DATA = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'data', 'plugins.json'))
CACHE = os.path.join(os.path.dirname(__file__), '..', 'audit-repos.cache.json')
REPORT = os.path.join(os.path.dirname(__file__), '..', 'audit-report.json')
SUSPECT = os.path.join(os.path.dirname(__file__), '..', 'audit-suspects.txt')

TOKEN = os.environ.get('GITHUB_TOKEN', '')

DSH_TOPICS = {'dsh-plugin', 'deepseek-harness'}
_lock = threading.Lock()
_save_lock = threading.Lock()
_done = 0
_total = 0


def gh(repo):
    req = urllib.request.Request('https://api.github.com/repos/' + repo, headers={
        'Authorization': 'Bearer ' + TOKEN,
        'User-Agent': 'dshbase-audit',
        'Accept': 'application/vnd.github+json',
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status, dict(r.headers), json.loads(r.read())


def fetch(repo):
    global _done
    for attempt in range(3):
        try:
            status, hdrs, data = gh(repo)
            rem = int(hdrs.get('X-RateLimit-Remaining', '5000'))
            if status == 200:
                return {
                    'full_name': data.get('full_name'),
                    'topics': data.get('topics', []),
                    'description': data.get('description') or '',
                    'archived': bool(data.get('archived')),
                    'fork': bool(data.get('fork')),
                    'stars': data.get('stargazers_count') or 0,
                    'language': data.get('language') or '',
                    'pushed_at': (data.get('pushed_at') or '')[:10],
                    'status': 'ok',
                }
            if status == 404:
                return {'status': 'gone'}
            if status in (403, 429):
                time.sleep(60)
                continue
            return {'status': f'http{status}'}
        except Exception as e:
            if attempt == 2:
                return {'status': 'err', 'err': str(e)}
            time.sleep(2 * (attempt + 1))
    return {'status': 'err'}


def classify(name, desc, topics):
    t = set(topics or [])
    if t & DSH_TOPICS:
        return 'dsh'
    text = (name + ' ' + (desc or '')).lower()
    if 'deepseek' in text or 'cordis' in text:
        return 'dsh-desc'
    if 'harness' in text:
        return 'harness-only'
    return 'suspect'


def save(cache):
    with _save_lock:
        json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def main():
    global _total, _done
    d = json.load(open(DATA, encoding='utf-8'))
    repo_map = {}
    for cat, items in d.items():
        for p in items:
            m = re.search(r'github\.com/([^/]+/[^/]+?)/?$', p.get('url') or '')
            if not m:
                continue
            key = m.group(1).removesuffix('.git').lower()
            repo_map.setdefault(key, []).append((cat, p))

    _total = len(repo_map)
    print(f'共 {len(repo_map)} 个唯一仓库', flush=True)

    cache = {}
    if os.path.exists(CACHE):
        try:
            cache = json.load(open(CACHE, encoding='utf-8'))
            print(f'缓存命中 {len(cache)} 个仓库', flush=True)
        except Exception:
            cache = {}

    todo = [r for r in repo_map if r not in cache]
    print(f'需拉取 {len(todo)} 个', flush=True)

    workers = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 8
    if todo:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(fetch, r): r for r in todo}
            for fut in as_completed(futs):
                r = futs[fut]
                try:
                    cache[r] = fut.result()
                except Exception as e:
                    cache[r] = {'status': 'err', 'err': str(e)}
                with _lock:
                    _done += 1
                    if _done % 100 == 0:
                        save(cache)
                        print(f'  已处理 {_done}/{len(todo)}（已落盘）', flush=True)
        save(cache)
        print(f'缓存已写 {CACHE}', flush=True)

    # 分类统计
    stats = {}
    rows = []
    for key, entries in repo_map.items():
        meta = cache.get(key) or {}
        if meta.get('status') != 'ok':
            cat = 'gone'
        else:
            name = entries[0][1].get('name', '')
            cat = classify(name, meta.get('description', ''), meta.get('topics', []))
        stats[cat] = stats.get(cat, 0) + 1
        rows.append({
            'repo': key,
            'name': entries[0][1].get('name', ''),
            'cat': entries[0][0],
            'class': cat,
            'topics': meta.get('topics', []),
            'description': meta.get('description', ''),
            'archived': meta.get('archived'),
            'stars': meta.get('stars'),
        })

    print('\n===== 审计结果 =====', flush=True)
    order = ['dsh', 'dsh-desc', 'harness-only', 'suspect', 'gone']
    for c in order:
        print(f'  {c:14} {stats.get(c, 0)}', flush=True)

    json.dump(rows, open(REPORT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    suspects = [r for r in rows if r['class'] in ('suspect', 'harness-only', 'gone')]
    with open(SUSPECT, 'w', encoding='utf-8') as f:
        f.write('# 非/疑似非 DSH 生态插件审计\n')
        for r in suspects:
            f.write(f"[{r['class']}] {r['name']}  ({r['repo']})  cat={r['cat']}  ★{r['stars']}\n")
            f.write(f"    {r['description'][:120]}\n")
            if r['topics']:
                f.write(f"    topics: {', '.join(r['topics'][:12])}\n")
    print(f'详细报告: {REPORT}', flush=True)
    print(f'疑似清单: {SUSPECT}（{len(suspects)} 条）', flush=True)


if __name__ == '__main__':
    main()
