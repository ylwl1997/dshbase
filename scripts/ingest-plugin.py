#!/usr/bin/env python3
"""标准插件收录流程：验证 + 收录 + 全局去重。

用法:
  GITHUB_TOKEN=xxx python scripts/ingest-plugin.py https://github.com/owner/repo \
      --category "UI Enhancements" --npm "@scope/pkg" --desc-zh "中文描述"

- 验证：仓库存在 / dsh-plugin topic / LICENSE / bundle 清单（cordis.patch.yml 等）
- 收录：写入 src/data/plugins.json，全局去重（按 name 和 repo）
- 输出：--json 时输出 JSON 结果供自动化使用，否则打印人类可读文本

退出码：0=收录/已存在，1=拒绝（缺条件）
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import date

DATA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "data", "plugins.json"))
API = "https://api.github.com"
BUNDLE_FILES = ("cordis.patch.yml", "cordis.yml", "dsh.bundle.patch", "dsh.bundle", "dsh.bundle.yml")

CATEGORIES = [
    "UI Enhancements", "Sessions & Messages", "Tools & Capabilities",
    "Workflow & Automation", "Notifications & Integrations",
    "Development & Runtime", "Just for Fun",
]


def gh(path):
    req = urllib.request.Request(API + path, headers={
        "Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
        "User-Agent": "dshbase-ingest",
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def parse_repo(url):
    m = re.search(r"github\.com/([^/\s]+)/([^/\s#?]+)", url or "")
    if not m:
        return None
    return f"{m.group(1)}/{m.group(2)}".rstrip(".git")


def fetch_repo(repo):
    try:
        return gh(f"/repos/{repo}")
    except Exception:
        return None


def fetch_files(repo):
    try:
        items = gh(f"/repos/{repo}/contents/")
        return [f.get("name", "") for f in items if isinstance(f, dict)]
    except Exception:
        return []


def verify(repo, data, files):
    """返回 (ok, issues, data)。issues 是缺失项列表。"""
    issues = []
    topics = data.get("topics", [])
    if "dsh-plugin" not in topics:
        issues.append("仓库未加 `dsh-plugin` topic")
    if not data.get("license"):
        issues.append("无 LICENSE 许可")
    if not any(f in files for f in BUNDLE_FILES):
        issues.append("无 bundle 清单（cordis.patch.yml 等）")
    return (len(issues) == 0, issues, data)


def build_entry(data, args):
    desc_en = (data.get("description") or "").strip()
    is_npm = bool(args.npm)
    return {
        "name": args.name or data["name"],
        "url": data["html_url"],
        "pkg": args.npm or "",
        "ver": "",
        "npm": is_npm,
        "test": "ui" if is_npm else "not-on-npm",
        "desc": desc_en or args.desc_zh or "",
        "desc_en": desc_en,
        "desc_zh": args.desc_zh or "",
        "stars": data.get("stargazers_count") or 0,
        "forks": data.get("forks_count") or 0,
        "issues": data.get("open_issues_count") or 0,
        "language": data.get("language") or "",
        "updated": (data.get("pushed_at") or "")[:10],
        "archived": bool(data.get("archived")),
        "added": date.today().isoformat(),
    }


def load_db():
    return json.load(open(DATA, encoding="utf-8"))


def find_existing(db, name, url):
    """全局查重：按 name（小写）或 repo 是否已存在。"""
    target_repo = parse_repo(url)
    for items in db.values():
        for p in items:
            if p["name"].lower() == name.lower():
                return p
            if target_repo and parse_repo(p.get("url")) == target_repo.lower():
                return p
    return None


def add_plugin(db, entry, category):
    cat = category if category in CATEGORIES else "Tools & Capabilities"
    if cat not in db:
        db[cat] = []
    db[cat].append(entry)
    db[cat].sort(key=lambda p: -(p.get("stars") or 0))
    json.dump(db, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", help="GitHub 仓库 URL 或 owner/name")
    ap.add_argument("--category", default="")
    ap.add_argument("--npm", default="", help="npm 包名（可选）")
    ap.add_argument("--name", default="", help="插件名（默认用仓库名）")
    ap.add_argument("--desc-zh", default="", help="中文描述")
    ap.add_argument("--json", action="store_true", help="输出 JSON 结果")
    args = ap.parse_args()

    repo = parse_repo(args.repo) or args.repo
    data = fetch_repo(repo)

    if data is None:
        result = {"status": "error", "message": f"仓库不存在或无法访问：{repo}"}
        print(json.dumps(result, ensure_ascii=False) if args.json else result["message"])
        sys.exit(1)

    files = fetch_files(repo)
    ok, issues, data = verify(repo, data, files)
    name = args.name or data["name"]
    entry = build_entry(data, args)

    db = load_db()
    existing = find_existing(db, name, data["html_url"])

    if not ok:
        msg = "❌ 暂时无法收录，缺少以下条件：\n\n" + "\n".join(f"- [ ] {i}" for i in issues) + "\n\n请补充后重新提交。"
        result = {"status": "rejected", "issues": issues, "message": msg}
    elif existing is not None:
        install = f"`dsh plugin add {existing['pkg']}`" if existing.get("pkg") else f"`dsh plugin add github:{repo}`"
        msg = f"✅ 该插件已在目录中（分类：{next(k for k,v in db.items() if any(p is existing for p in v))}），无需重复收录。安装：{install}"
        result = {"status": "existing", "name": name, "message": msg}
    else:
        add_plugin(db, entry, args.category)
        install = f"`dsh plugin add {entry['pkg']}`" if entry["pkg"] else f"`dsh plugin add github:{repo}`"
        msg = (f"✅ 已收录。\n\n- 分类：{args.category or 'Tools & Capabilities'}\n"
               f"- 安装：{install}\n- 验证：仓库 ✓ · dsh-plugin topic ✓ · license ✓ · bundle ✓\n\n感谢提交！")
        result = {"status": "accepted", "name": name, "category": args.category, "install": install, "message": msg}

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(result["message"])
    sys.exit(0 if result["status"] in ("accepted", "existing") else 1)


if __name__ == "__main__":
    main()
