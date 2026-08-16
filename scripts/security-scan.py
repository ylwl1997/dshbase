#!/usr/bin/env python3
"""静态安全扫描：对插件的源码做启发式检查，写回 src/data/security.json。

对齐 dsh.so 的「安全扫描」思路（硬编码密钥 / 危险命令 / 数据外传 / 越权请求），
但口径诚实：这是静态正则特征扫描，不是安全审计，也绝不背书第三方代码。

启发式四类：
  secrets            硬编码密钥（AWS/Google/GitHub/Slack/Stripe/OpenAI/私钥）
  dangerous-cmd      破坏性或任意执行（rm -rf /、curl|sh、eval、shell=True 等）
  exfil              数据外传回调（webhook URL、burpcollab、canarytokens 等）
  permissions        越权文件/子进程访问（fs.writeFile、child_process.exec 等）

风险分级：critical > high > medium > low（无发现）

用法：
  GITHUB_TOKEN=xxx python scripts/security-scan.py              # 扫描 top 100（按星）
  GITHUB_TOKEN=xxx python scripts/security-scan.py --limit 20   # 扫描 top 20
  GITHUB_TOKEN=xxx python scripts/security-scan.py owner/repo   # 扫描单个仓库
"""
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone

DB = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'data', 'plugins.json'))
OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'data', 'security.json'))

# 值得扫的文件扩展名（跳过二进制/大文件/锁文件）
EXT = ('.js', '.ts', '.jsx', '.tsx', '.mjs', '.cjs', '.py', '.sh', '.bash', '.yml', '.yaml', '.json', '.toml', '.md')
SKIP_DIRS = ('node_modules', 'dist', 'build', '.git', 'vendor', '.next', 'coverage', 'public/assets')
MAX_FILES = 25          # 每个仓库最多扫的文件数
MAX_SIZE = 200_000      # 单文件字节上限
REPO_BUDGET = 60        # 单仓库扫描的墙钟时间预算（秒），超过则截断，避免大仓库拖垮整体

# (分类, 严重度, 正则)
PATTERNS = [
    ('secrets', 'critical', re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----')),
    ('secrets', 'critical', re.compile(r'\bAKIA[0-9A-Z]{16}\b')),
    ('secrets', 'high', re.compile(r'\bAIza[0-9A-Za-z_-]{30,}\b')),
    ('secrets', 'high', re.compile(r'\bgh[pousr]_[A-Za-z0-9]{20,}\b')),
    ('secrets', 'high', re.compile(r'\bgithub_pat_[A-Za-z0-9_]{20,}\b')),
    ('secrets', 'high', re.compile(r'\bxox[baprs]-[A-Za-z0-9-]{10,}\b')),
    ('secrets', 'high', re.compile(r'\b(?:sk|pk)_(?:live|test)_[A-Za-z0-9]{16,}\b')),
    ('secrets', 'high', re.compile(r'\bsk-[A-Za-z0-9]{20,}\b')),
    ('dangerous-cmd', 'high', re.compile(r'\brm\s+-rf\s+[/~]')),
    ('dangerous-cmd', 'high', re.compile(r'(?:curl|wget)\b[^|\n]*\|\s*(?:sudo\s+)?(?:ba)?sh')),
    ('dangerous-cmd', 'high', re.compile(r'\beval\s*\(')),
    ('dangerous-cmd', 'high', re.compile(r'\b(?:child_process\.exec|execSync|spawn)\s*\(')),
    ('dangerous-cmd', 'high', re.compile(r'\bos\.system\s*\(|\bsubprocess\.(?:call|Popen)\s*\([^)]*shell\s*=\s*True')),
    ('exfil', 'high', re.compile(r'https?://(?:hooks\.slack\.com/services/|(?:www\.)?discord(?:app)?\.com/api/webhooks/)')),
    ('exfil', 'high', re.compile(r'(?:webhook\.site|burpcollaborator\.net|oast\.(?:fun|pro|live)|interact\.sh|canarytokens\.com|requestbin\.(?:com|net))')),
    ('permissions', 'medium', re.compile(r'\b(?:fs\.(?:writeFile|writeFileSync|unlink|unlinkSync|rm|rmSync)|child_process\.exec)\b')),
    ('permissions', 'medium', re.compile(r'\bshell\s*:\s*true\b')),
    ('permissions', 'medium', re.compile(r'\bnetwork\.external\b')),
]

# 风险排序（用于取最高）
SEV_ORDER = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}


def gh(path):
    req = urllib.request.Request('https://api.github.com' + path, headers={
        'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'],
        'User-Agent': 'dshbase-security',
        'Accept': 'application/vnd.github+json',
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def raw(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'dshbase-security'})
    with urllib.request.urlopen(req, timeout=12) as r:
        data = r.read()
    return data.decode('utf-8', errors='replace')


def scan_text(text):
    findings = []
    for cat, sev, rx in PATTERNS:
        if rx.search(text):
            findings.append({'cat': cat, 'sev': sev})
    # 去重：同 category 只记一次，取最高严重度
    seen = {}
    for f in findings:
        if f['cat'] not in seen or SEV_ORDER[f['sev']] > SEV_ORDER[seen[f['cat']]['sev']]:
            seen[f['cat']] = f
    return list(seen.values())


def scan_repo(name, url):
    """返回 {'risk':..., 'findings':[...], 'files':N, 'scannedAt':...}，失败返回 None。"""
    repo = (url or '').replace('https://github.com/', '').rstrip('/')
    if not repo:
        return None
    try:
        meta = gh(f'/repos/{repo}')
        branch = meta.get('default_branch', 'main')
        tree = gh(f'/repos/{repo}/git/trees/{branch}?recursive=1')
        paths = [t['path'] for t in tree.get('tree', [])
                 if t.get('type') == 'blob' and t.get('path', '').endswith(EXT)]
    except Exception as e:
        print(f'  ! {name}: tree fetch failed ({e})')
        return None

    # 过滤 + 限量
    paths = [p for p in paths if not any(f'/{d}/' in f'/{p}' for d in SKIP_DIRS)]
    if len(paths) > MAX_FILES:
        # 优先源码文件，去重后截断
        paths = paths[:MAX_FILES]

    findings = []
    scanned = 0
    deadline = time.time() + REPO_BUDGET
    for p in paths:
        if time.time() > deadline:
            break
        try:
            text = raw(f'https://raw.githubusercontent.com/{repo}/{branch}/{p}')
        except Exception:
            continue
        if len(text) > MAX_SIZE:
            continue
        scanned += 1
        findings.extend(scan_text(text))

    # 去重 + 汇总风险
    seen = {}
    for f in findings:
        if f['cat'] not in seen or SEV_ORDER[f['sev']] > SEV_ORDER[seen[f['cat']]['sev']]:
            seen[f['cat']] = f
    uniq = list(seen.values())
    if any(f['sev'] == 'critical' for f in uniq):
        risk = 'critical'
    elif any(f['sev'] == 'high' for f in uniq):
        risk = 'high'
    elif any(f['sev'] == 'medium' for f in uniq):
        risk = 'medium'
    else:
        risk = 'low'
    return {
        'risk': risk,
        'findings': uniq,
        'files': scanned,
        'scannedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }


def main():
    d = json.load(open(DB, encoding='utf-8'))
    allp = [p for items in d.values() for p in items]

    # 已有结果保留（增量合并）
    existing = {}
    if os.path.exists(OUT):
        existing = json.load(open(OUT, encoding='utf-8'))

    if len(sys.argv) > 1 and '/' in sys.argv[1]:
        targets = [p for p in allp if (p.get('url') or '').replace('https://github.com/', '').rstrip('/') == sys.argv[1]]
    else:
        limit = 100
        if '--limit' in sys.argv:
            limit = int(sys.argv[sys.argv.index('--limit') + 1])
        targets = sorted(allp, key=lambda p: -(p.get('stars') or 0))[:limit]

    done = 0
    for p in targets:
        res = scan_repo(p['name'], p.get('url'))
        if res is None:
            continue
        existing[p['name']] = res
        done += 1
        fsum = ', '.join(f"{f['cat']}:{f['sev']}" for f in res['findings']) or 'clean'
        print(f'[{done}/{len(targets)}] {p["name"]}: {res["risk"]} ({res["files"]} files) — {fsum}')

    json.dump(existing, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\nsecurity.json: {len(existing)} scanned -> {OUT}')


if __name__ == '__main__':
    main()
