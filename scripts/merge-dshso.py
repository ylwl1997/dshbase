#!/usr/bin/env python3
"""从 dsh.so 的 search-index.json + 详情页对接插件目录，追平数量并富化元数据。

做的事：
  1. 拉 https://www.dsh.so/search-index.json（1814 插件元数据：分类/use-case/信任/安全/健康/描述）
  2. 线程池抓 dsh.so 详情页，提取每个插件的 GitHub 仓库 URL + license（缓存到 /tmp）
  3. 与我们 src/data/plugins.json 合并：补 763 个缺的插件（test=pending / 未验证），
     并为所有插件补 license / ucs(use-cases) / trust 字段
  4. 分类从 7 扩到 15（dsh.so 19 类合并为 15 类），use-case 作为第二轴（10 个）

新增字段（向后兼容，不影响现有脚本）：
  license  协议（MIT/Apache-2.0/... 或 ""）
  ucs      use-cases 列表（["File","Memory",...]，可为空）
  trust    信任等级（Silver/Bronze/Unrated）

用法：python scripts/merge-dshso.py [--dry-run]
"""
import json
import os
import re
import sys
import tempfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DB = os.path.join(ROOT, 'src', 'data', 'plugins.json')
CACHE = os.path.join(tempfile.gettempdir(), 'dshso_detail_cache.json')
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36'}

# 15 类（dsh.so 19 类合并而来）。key=新类，value=来源类列表
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
# 反向：dsh.so 类 -> 我们的新类
THEIR_CAT_TO_NEW = {}
for new, srcs in CAT_MERGE.items():
    for s in srcs:
        THEIR_CAT_TO_NEW[s] = new

# 我们旧 7 类 -> 新 15 类
OUR_CAT_TO_NEW = {
    'UI Enhancements': 'UI & Skins',
    'Sessions & Messages': 'Knowledge',
    'Tools & Capabilities': 'Developer',
    'Workflow & Automation': 'Automation',
    'Notifications & Integrations': 'Network',
    'Development & Runtime': 'Developer',
    'Just for Fun': 'UI & Skins',
}

USE_CASES = ['Terminal / Shell', 'File', 'Vision / OCR', 'Memory', 'Database',
             'Web search', 'Storage', 'GitHub integration', 'Code review', 'Notifications']


def http_get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', errors='replace')


def parse_stars(s):
    if s is None:
        return 0
    s = str(s).strip().lower().replace(',', '')
    m = re.match(r'([\d.]+)\s*([km]?)', s)
    if not m:
        return 0
    v = float(m.group(1))
    unit = m.group(2)
    if unit == 'k':
        v *= 1000
    elif unit == 'm':
        v *= 1000000
    return int(v)


def fetch_detail(slug):
    """抓 dsh.so 详情页，返回 {repo, license, owner}。失败返回 None。"""
    for base in (f'https://www.dsh.so/artifact/{slug}/', f'https://www.dsh.so/plugins/{slug}/'):
        try:
            h = http_get(base)
            links = re.findall(r'https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)', h)
            repo = None
            for l in links:
                if l.startswith(('deepseek-ai/', 'ihuajiu/')):
                    continue
                repo = l
                break
            if not repo:
                continue
            m = re.search(r'License</strong></td><td>([^<]*)</td>', h)
            license_ = m.group(1).strip() if m else ''
            owner = repo.split('/')[0]
            return {'repo': repo, 'license': license_, 'owner': owner}
        except Exception:
            continue
    return None


def load_their_index():
    data = json.loads(http_get('https://www.dsh.so/search-index.json'))
    return [x for x in data if x.get('name') != 'deepseek-harness']


def main():
    dry = '--dry-run' in sys.argv
    their = load_their_index()
    print(f'dsh.so 插件: {len(their)}')

    d = json.load(open(DB, encoding='utf-8'))
    # 记住旧分类（dict key），展平
    our = {}
    for cat, items in d.items():
        for p in items:
            our[p['name']] = (p, cat)
    print(f'我们插件: {len(our)}')

    missing = [x for x in their if x['name'] not in our]
    overlap = [x for x in their if x['name'] in our]
    print(f'需导入: {len(missing)}，重合: {len(overlap)}')

    # 抓详情页（全部 their，缓存）
    cache = {}
    if os.path.exists(CACHE):
        cache = json.load(open(CACHE, encoding='utf-8'))
    todo = [x['slug'] for x in their if x['slug'] not in cache]
    print(f'抓详情页 {len(todo)} 个（缓存 {len(cache)}）…')
    with ThreadPoolExecutor(max_workers=30) as ex:
        futs = {ex.submit(fetch_detail, s): s for s in todo}
        done = 0
        for f in as_completed(futs):
            slug = futs[f]
            r = f.result()
            if r:
                cache[slug] = r
            done += 1
            if done % 200 == 0:
                print(f'  {done}/{len(todo)}')
    json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)

    # 构建合并结果
    today = date.today().isoformat()
    newdb = {k: [] for k in CAT_MERGE}

    def primary_cat(new_cats):
        for c in new_cats:
            if c in newdb:
                return c
        return 'Developer'

    # 1) 已有插件：补字段 + 换分类
    for name, (p, old_cat) in our.items():
        new_cat = OUR_CAT_TO_NEW.get(old_cat, 'Developer')
        # 从 their 元数据补 license/ucs/trust（若有）
        their_meta = next((x for x in their if x['name'] == name), None)
        p.setdefault('license', '')
        p.setdefault('ucs', [])
        p.setdefault('trust', 'Unrated')
        if their_meta:
            slug = their_meta['slug']
            det = cache.get(slug)
            if det and det.get('license'):
                p['license'] = det['license']
            p['ucs'] = [u for u in their_meta.get('ucs', []) if u in USE_CASES]
            p['trust'] = their_meta.get('trust', 'Unrated')
        newdb[new_cat].append(p)

    # 2) 导入缺的插件（pending）
    for x in missing:
        slug = x['slug']
        det = cache.get(slug)
        if not det:
            print(f'  ! 跳过 {x["name"]}（无详情/无 repo）')
            continue
        new_cats = [THEIR_CAT_TO_NEW.get(c) for c in x.get('cats', [])]
        new_cats = [c for c in new_cats if c]
        cat = primary_cat(new_cats) if new_cats else 'Developer'
        entry = {
            'name': x['name'],
            'url': 'https://github.com/' + det['repo'],
            'pkg': '',
            'ver': '',
            'npm': False,
            'test': 'pending',
            'desc': x.get('description', ''),
            'desc_en': x.get('description', ''),
            'desc_zh': '',
            'stars': parse_stars(x.get('stars')),
            'forks': 0,
            'issues': 0,
            'language': '',
            'updated': '',
            'archived': x.get('health') == 'Archived',
            'added': today,
            'license': det.get('license', ''),
            'ucs': [u for u in x.get('ucs', []) if u in USE_CASES],
            'trust': x.get('trust', 'Unrated'),
        }
        newdb[cat].append(entry)

    total = sum(len(v) for v in newdb.values())
    print(f'\n合并后总数: {total}')
    for c in CAT_MERGE:
        if newdb[c]:
            print(f'  {c}: {len(newdb[c])}')

    if dry:
        print('\n[dry-run] 未写盘')
        return

    json.dump(newdb, open(DB, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\n已写回 {DB}')


if __name__ == '__main__':
    main()
