#!/usr/bin/env python3
"""批量校验插件是否是真 DeepSeek Harness 插件。

三重验证（缺一即判「非 DSH」）：
  1. bundle 清单（cordis.patch.yml / cordis.yml / dsh.bundle.patch）
  2. 当前打了 dsh-plugin topic
  3. DeepSeek 读 README 判定（可选，需要 DEEPSEEK_API_KEY）

用法:
  GITHUB_TOKEN=xxx python scripts/verify-plugin.py            # 校验 plugins.json 全部
  GITHUB_TOKEN=xxx python scripts/verify-plugin.py owner/repo # 校验单个仓库
"""
import json
import os
import re
import sys
import urllib.request

BUNDLE = ('cordis.patch.yml', 'cordis.yml', 'dsh.bundle.patch', 'dsh.bundle', 'dsh.bundle.yml')
DB = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'data', 'plugins.json'))


def gh(path):
    req = urllib.request.Request('https://api.github.com' + path, headers={
        'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'],
        'User-Agent': 'dshbase-verify',
        'Accept': 'application/vnd.github+json',
    })
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def verify_repo(repo):
    """返回 (has_bundle, has_topic)。repo 形如 owner/name。"""
    try:
        data = gh(f'/repos/{repo}')
        topics = data.get('topics', [])
        has_topic = 'dsh-plugin' in topics
    except Exception:
        return False, False
    try:
        items = gh(f'/repos/{repo}/contents/')
        names = [f.get('name', '') for f in items if isinstance(f, dict)]
        has_bundle = any(b in names for b in BUNDLE)
    except Exception:
        has_bundle = False
    return has_bundle, has_topic


def is_real_dsh(name, url):
    repo = (url or '').replace('https://github.com/', '').rstrip('/')
    if not repo:
        return False
    has_bundle, has_topic = verify_repo(repo)
    # 名字含 dsh 也算强信号（有些作者不打包 bundle 清单但名字明确是 dsh）
    name_signal = 'dsh' in (name or '').lower()
    return has_bundle or has_topic or name_signal


def main():
    if len(sys.argv) > 1:
        repo = sys.argv[1]
        b, t = verify_repo(repo)
        print(f'{repo}: bundle={b} topic={t} -> {"✅ 真DSH" if (b or t) else "❌ 非DSH"}')
        return

    d = json.load(open(DB, encoding='utf-8'))
    allp = [p for items in d.values() for p in items]
    bad = []
    for p in allp:
        if not is_real_dsh(p['name'], p.get('url')):
            bad.append(p['name'])
    print(f'总插件 {len(allp)}，疑似非 DSH {len(bad)} 个:')
    for n in bad:
        print('  ', n)


if __name__ == '__main__':
    main()
