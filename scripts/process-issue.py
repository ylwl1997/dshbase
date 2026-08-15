#!/usr/bin/env python3
"""GitHub Actions：自动处理插件收录 issue。

从环境变量读取 issue 号与正文，解析出仓库/分类/npm/描述，调用 ingest-plugin.py
验证收录，然后评论结果并（收录时）关闭 issue。

环境变量：ISSUE_NUMBER, ISSUE_BODY, GITHUB_TOKEN
"""
import json
import os
import re
import subprocess
import sys
import urllib.request

BASE = "https://api.github.com/repos/ylwl1997/dshbase"


def headers():
    return {
        "Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
        "User-Agent": "dshbase-ingest",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }


def sec(body, title):
    m = re.search(title + r"[^\n]*\n\n(.+?)(?=\n\n###|\Z)", body, re.S)
    return (m.group(1).strip() if m else "")


def parse(body):
    name = sec(body, r"### 插件名称")
    repo = sec(body, r"### GitHub 仓库")
    npm = sec(body, r"### npm 包名")
    desc_zh = sec(body, r"### 功能描述")
    category = sec(body, r"### 分类")

    # npm 清理：跳过「_No response_」「暂无」等
    npm_lower = npm.lower().strip()
    if not npm or npm_lower in ("_no response_", "no response", "none", "暂无") or npm.startswith("暂无"):
        npm = ""

    # 分类：取括号前英文部分
    category = re.split(r"[（(]", category)[0].strip()

    # 仓库：提取 URL
    m = re.search(r"https?://github\.com/[^\s]+", repo)
    repo_url = m.group(0) if m else repo.strip()

    return name, repo_url, npm, desc_zh, category


def post_comment(n, body):
    data = json.dumps({"body": body}).encode()
    req = urllib.request.Request(f"{BASE}/issues/{n}/comments", data=data, headers=headers())
    urllib.request.urlopen(req)


def close_issue(n):
    data = json.dumps({"state": "closed"}).encode()
    req = urllib.request.Request(f"{BASE}/issues/{n}", data=data, headers=headers(), method="PATCH")
    urllib.request.urlopen(req)


def main():
    n = os.environ["ISSUE_NUMBER"]
    body = os.environ.get("ISSUE_BODY", "")
    name, repo_url, npm, desc_zh, category = parse(body)

    if not repo_url:
        post_comment(n, "❌ 未在 issue 里找到有效的 GitHub 仓库地址，请按模板填写「GitHub 仓库」字段。")
        print("no repo url")
        return

    cmd = [sys.executable, "scripts/ingest-plugin.py", repo_url, "--json"]
    if category:
        cmd += ["--category", category]
    if npm:
        cmd += ["--npm", npm]
    if name:
        cmd += ["--name", name]
    if desc_zh:
        cmd += ["--desc-zh", desc_zh]

    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        result = json.loads(r.stdout)
    except Exception:
        post_comment(n, "❌ 处理出错，请稍后重试或联系维护者。\n\n" + r.stderr[-500:])
        return

    post_comment(n, result.get("message", "已处理"))
    if result.get("status") in ("accepted", "existing"):
        close_issue(n)
    print(f"#{n} -> {result.get('status')} {result.get('name', '')}")


if __name__ == "__main__":
    main()
