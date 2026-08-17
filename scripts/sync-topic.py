#!/usr/bin/env python3
"""从 GitHub dsh-plugin topic 直接同步插件数据。

用法: GITHUB_TOKEN=xxx python scripts/sync-topic.py [--dry-run]

- 拉取 topic:dsh-plugin 全部仓库（search API，按 stars 降序，最多 1000）
- 对 plugins.json 里匹配到的仓库，刷新 stars/forks/description/language/pushed_at/archived
- 报告：topic 总数、匹配数、新增可收录仓库
"""
import json
import os
import re
import sys
import time
import urllib.request

API = "https://api.github.com"
DATA = os.path.join(os.path.dirname(__file__), "..", "src", "data", "plugins.json")
DATA = os.path.abspath(DATA)

def gh(path):
    req = urllib.request.Request(API + path, headers={
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "User-Agent": "dshbase-sync",
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def fetch_topic():
    repos = {}
    page = 1
    total = 0
    while page <= 10:  # search API 上限 1000 结果
        data = gh(f"/search/repositories?q=topic:dsh-plugin&sort=stars&order=desc&per_page=100&page={page}")
        total = data.get("total_count", 0)
        items = data.get("items", [])
        if not items:
            break
        for it in items:
            repos[it["full_name"].lower()] = it
        if len(repos) >= total:
            break
        page += 1
        time.sleep(1.2)
    return repos, total

def repo_key(url):
    m = re.search(r"github\.com/([^/]+)/([^/]+?)/?$", url or "")
    if not m:
        return None
    return f"{m.group(1)}/{m.group(2)}".removesuffix(".git").lower()

def main():
    dry = "--dry-run" in sys.argv
    repos, total = fetch_topic()
    print(f"topic:dsh-plugin 共 {total} 个仓库，拉到 {len(repos)} 个（top 1000 by stars）")

    d = json.load(open(DATA, encoding="utf-8"))
    matched = 0
    updated = 0
    missing = 0
    new_available = []

    for items in d.values():
        for p in items:
            key = repo_key(p.get("url"))
            if not key:
                continue
            if key in repos:
                matched += 1
                it = repos[key]
                if (p.get("stars") != it.get("stargazers_count")
                        or p.get("forks") != it.get("forks_count")
                        or p.get("issues") != it.get("open_issues_count")
                        or p.get("language") != it.get("language")
                        or p.get("archived") != bool(it.get("archived"))):
                    p["stars"] = it.get("stargazers_count") or 0
                    p["forks"] = it.get("forks_count") or 0
                    p["issues"] = it.get("open_issues_count") or 0
                    p["language"] = it.get("language") or p.get("language")
                    p["updated"] = (it.get("pushed_at") or p.get("updated"))[:10]
                    p["archived"] = bool(it.get("archived"))
                    updated += 1
            else:
                missing += 1

    # 我们目录里没有、但 topic 里有的仓库（候选新增）
    ours = {repo_key(p.get("url")) for items in d.values() for p in items}
    for key, it in repos.items():
        if key not in ours and not it.get("archived") and not it.get("fork"):
            new_available.append((it.get("stargazers_count") or 0, key, (it.get("description") or "")[:60]))

    new_available.sort(reverse=True)

    print(f"匹配: {matched}  刷新字段: {updated}  未匹配(长尾): {missing}")
    print(f"候选新增(top 20, 未归档非 fork):")
    for stars, name, desc in new_available[:20]:
        print(f"  ★{stars:<6} {name:45} {desc}")

    if not dry and updated:
        json.dump(d, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"已写入 {DATA}（更新 {updated} 个插件）")
    elif dry:
        print("dry-run：未写入")

    # 写更新日期（无论是否 dry-run 都记录，用于页面「更新于」标注）
    from datetime import date
    today = date.today().isoformat()
    SYNC = os.path.join(os.path.dirname(DATA), "sync-date.json")
    if not dry:
        json.dump({"updated": today}, open(SYNC, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"已写入 {SYNC}（updated={today}）")

if __name__ == "__main__":
    main()
