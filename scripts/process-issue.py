#!/usr/bin/env python3
"""GitHub Actions / on-call：自动处理插件收录 issue。

从环境变量读取 issue 号与正文，解析出仓库/分类/npm/描述，调用 ingest-plugin.py
验证收录，刷新可信贡献者，然后评论结果并（收录时）关闭 issue。

环境变量：ISSUE_NUMBER, ISSUE_BODY, GITHUB_TOKEN
可选：ISSUE_AUTHOR（提交者 login；缺省时从 Issue API 读取）
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

    npm_lower = npm.lower().strip()
    if not npm or npm_lower in ("_no response_", "no response", "none", "暂无") or npm.startswith("暂无"):
        npm = ""

    category = re.split(r"[（(]", category)[0].strip()

    m = re.search(r"https?://github\.com/[^\s]+", repo)
    repo_url = m.group(0) if m else repo.strip()

    return name, repo_url, npm, desc_zh, category


def api_get(path):
    req = urllib.request.Request(BASE + path, headers=headers())
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())


def post_comment(n, body):
    data = json.dumps({"body": body}).encode()
    req = urllib.request.Request(f"{BASE}/issues/{n}/comments", data=data, headers=headers())
    urllib.request.urlopen(req)


def close_issue(n):
    data = json.dumps({"state": "closed"}).encode()
    req = urllib.request.Request(f"{BASE}/issues/{n}", data=data, headers=headers(), method="PATCH")
    urllib.request.urlopen(req)


def refresh_contributor(author: str, plugin_name: str) -> tuple[bool, str]:
    """刷新 contributors.json，并断言作者已入库。返回 (ok, detail)."""
    if not author:
        return False, "missing issue author login"
    cmd = [
        sys.executable,
        "scripts/fetch-contributors.py",
        "--quiet",
        "--ensure-author",
        author,
        "--ensure-plugin",
        plugin_name,
        "--require",
        author,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    detail = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()[-800:]
    return r.returncode == 0, detail


def main():
    n = os.environ["ISSUE_NUMBER"]
    body = os.environ.get("ISSUE_BODY", "")
    name, repo_url, npm, desc_zh, category = parse(body)

    author = (os.environ.get("ISSUE_AUTHOR") or "").strip()
    if not author:
        try:
            author = api_get(f"/issues/{n}")["user"]["login"]
        except Exception as e:
            print(f"warn: could not resolve issue author: {e}", file=sys.stderr)

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
        post_comment(n, "❌ 处理出错，请稍后重试或联系维护者。\n\n" + (r.stderr or "")[-500:])
        return

    msg = result.get("message", "已处理")
    plugin_name = result.get("name") or name

    if result.get("status") in ("accepted", "existing"):
        # 硬门槛：提交者必须进入可信贡献者页，否则不算收录完成
        ok, detail = refresh_contributor(author, plugin_name)
        if not ok:
            fail = (
                "⚠️ 插件已写入目录，但刷新可信贡献者失败"
                + (f"（作者 `{author}`）" if author else "")
                + "，请维护者检查后补跑 `scripts/fetch-contributors.py`。\n\n"
                + f"<details><summary>日志</summary>\n\n```\n{detail}\n```\n</details>"
            )
            post_comment(n, msg + "\n\n" + fail)
            print(f"#{n} -> {result.get('status')} but contributor refresh FAILED")
            sys.exit(1)

        msg += (
            f"\n\n- 可信贡献者：已将 @{author} 加入"
            " https://dshbase.com/contributors/ "
            "（中文：https://dshbase.com/zh/contributors/）"
        )
        post_comment(n, msg)
        close_issue(n)
    else:
        post_comment(n, msg)

    print(f"#{n} -> {result.get('status')} {result.get('name', '')} author={author}")


if __name__ == "__main__":
    main()
