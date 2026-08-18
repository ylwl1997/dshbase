#!/usr/bin/env python3
"""插件详情页富化数据管道：拉 contributors 数 / Builds on N 官方包数 / README 转 HTML。

用法:
  GITHUB_TOKEN=xxx python scripts/fetch-repo-enrich.py [--limit 100] [--start 0]

- contributors:  GitHub REST /repos/{o}/{r}/contributors?per_page=1&anon=1，从 Link header 的 last 页号取总数
- depsOfficial:  npm 源统计 registry dependencies 里 @deepseek-ai/* 数；git 源读 raw package.json
- README:        GitHub /repos/{o}/{r}/readme (raw) 或 npm readme，marked 转 HTML 存 readmes.json

输出:
  src/data/readmes.json           { slug: {html, updatedAt} }
  plugins.json 写回 contributors / depsOfficial / repoOwner 字段

限流: --limit N 默认 100；已拉取且有 updatedAt 的跳过（--force 重拉）。
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "src", "data", "plugins.json")
README_OUT = os.path.join(ROOT, "src", "data", "readmes.json")
API = "https://api.github.com"
NPM = "https://registry.npmjs.org"

TOKEN = os.environ.get("GITHUB_TOKEN", "")
HDRS = {"User-Agent": "dshbase-enrich", "Accept": "application/vnd.github+json"}
if TOKEN:
    HDRS["Authorization"] = "Bearer " + TOKEN


def gh(path, raw=False, timeout=20):
    hdr = dict(HDRS)
    if raw:
        hdr["Accept"] = "application/vnd.github.raw"
    req = urllib.request.Request(API + path, headers=hdr)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        if raw:
            return r.read().decode("utf-8", errors="replace")
        return (json.loads(r.read()), dict(r.headers))


def gh_headers(path, timeout=20):
    req = urllib.request.Request(API + path, headers=HDRS, method="HEAD")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return dict(r.headers)


def parse_repo(url):
    m = re.search(r"github\.com/([^/\s]+)/([^/\s#?]+)", url or "")
    if not m:
        return None
    return f"{m.group(1)}/{m.group(2)}".removesuffix(".git")


def fetch_contributors(repo):
    """contributors 总数：per_page=1 拿 Link header last 页号。"""
    try:
        hdrs = gh_headers(f"/repos/{repo}/contributors?per_page=1&anon=1")
        link = hdrs.get("Link", "")
        m = re.search(r'page=(\d+)>; rel="last"', link)
        return int(m.group(1)) if m else (1 if "page=" in link else 0)
    except Exception:
        return 0


def fetch_deps(repo, pkg):
    """Builds on N official DSH packages。统计 dependencies + peerDependencies 里的 @deepseek-ai/*。
    npm 源从 registry；git 源从 raw package.json。devDependencies 不算（构建工具非运行时）。"""
    deps = {}
    peers = {}
    if pkg:
        try:
            with urllib.request.urlopen(NPM + "/" + pkg.replace("/", "%2F"), timeout=20) as r:
                d = json.loads(r.read())
            v = d["dist-tags"]["latest"]
            deps = d["versions"][v].get("dependencies", {})
            peers = d["versions"][v].get("peerDependencies", {})
        except Exception:
            deps = {}
    elif repo:
        try:
            with urllib.request.urlopen(
                    f"https://raw.githubusercontent.com/{repo}/main/package.json", timeout=20) as r:
                d = json.loads(r.read())
            deps = d.get("dependencies", {})
            peers = d.get("peerDependencies", {})
        except Exception:
            try:
                with urllib.request.urlopen(
                        f"https://raw.githubusercontent.com/{repo}/master/package.json", timeout=20) as r:
                    d = json.loads(r.read())
                deps = d.get("dependencies", {})
                peers = d.get("peerDependencies", {})
            except Exception:
                deps = {}
    merged = {**deps, **peers}
    official = sum(1 for k in merged if k.startswith("@deepseek-ai/"))
    return len(merged), official


def fetch_readme(repo, pkg):
    """README 原文（优先 GitHub，npm 源兜底 registry readme）。"""
    if repo:
        try:
            return gh(f"/repos/{repo}/readme", raw=True)
        except Exception:
            pass
    if pkg:
        try:
            with urllib.request.urlopen(NPM + "/" + pkg.replace("/", "%2F"), timeout=20) as r:
                d = json.loads(r.read())
            v = d["dist-tags"]["latest"]
            rm = d["versions"][v].get("readme") or d.get("readme")
            if rm:
                return rm
        except Exception:
            pass
    return ""


def detect_branch(repo):
    """探测仓库默认分支（main/master）。"""
    for b in ("main", "master"):
        try:
            with urllib.request.urlopen(f"https://raw.githubusercontent.com/{repo}/{b}/package.json", timeout=10):
                return b
        except Exception:
            continue
    return "main"


def sanitize_html(html, repo=None, branch="main"):
    """剥离第三方 README 里的危险内容；相对路径资源重写为 GitHub raw URL。"""
    # 1. 删 script/style/iframe/object/embed
    html = re.sub(r'<(script|style|iframe|object|embed|form)\b.*?</\1>', '', html, flags=re.S | re.I)
    html = re.sub(r'<script\b[^>]*>.*', '', html, flags=re.S | re.I)  # 未闭合的兜底
    # 2. 删 on* 事件属性
    html = re.sub(r'\son\w+\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)', '', html, flags=re.I)
    # 3. 禁 javascript:/data: 协议链接
    html = re.sub(r'(href|src)\s*=\s*(["\'])\s*(?:javascript|data|vbscript):[^"\']*\2', r'\1=\2#\2', html, flags=re.I)
    # 4. 相对路径 → GitHub raw（src/href 非绝对、非锚点、非 mailto/data）
    if repo:
        base = f"https://raw.githubusercontent.com/{repo}/{branch}/"
        def _rw(m):
            attr, path = m.group(1), m.group(2)
            if path.startswith(("#", "mailto:", "data:", "http")):
                return m.group(0)
            clean = path.lstrip("./")
            return f'{attr}="{base}{clean}"'
        html = re.sub(r'(src|href)="([^"]*)"', _rw, html)
    return html


def to_html(md, repo=None, branch="main"):
    """markdown → HTML（用 marked，node 侧），后处理 sanitize + 相对路径重写。"""
    if not md:
        return ""
    import subprocess
    try:
        r = subprocess.run(
            ["node", "-e", "const {marked}=require('marked');let s='';process.stdin.on('data',d=>s+=d).on('end',()=>process.stdout.write(marked.parse(s,{breaks:true})))"],
            input=md, capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and r.stdout.strip():
            return sanitize_html(r.stdout, repo, branch)
    except Exception:
        pass
    # fallback: 基本转义 + 段落
    import html as _html
    esc = _html.escape(md)
    esc = re.sub(r"^#{1,4} (.+)$", r"<h2>\1</h2>", esc, flags=re.M)
    esc = re.sub(r"`([^`]+)`", r"<code>\1</code>", esc)
    esc = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\1" rel="noopener">\2</a>', esc)
    return f"<div class=\"readme-fallback\">{esc}</div>"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    db = json.load(open(DATA, encoding="utf-8"))
    readmes = {}
    if os.path.exists(README_OUT):
        readmes = json.load(open(README_OUT, encoding="utf-8"))

    # 扁平化待处理列表
    allp = []
    for items in db.values():
        for p in items:
            allp.append(p)
    total = len(allp)
    done = updated = 0
    for i, p in enumerate(allp[args.start:args.start + args.limit], 1):
        name = p["name"]
        repo = parse_repo(p.get("url"))
        pkg = p.get("pkg") or ""
        if not repo and not pkg:
            continue
        # 跳过已富化且未强制（按 updated 缓存）
        prev = p.get("_enriched") or ""
        cur = f"{p.get('updated')}|{p.get('ver')}"
        if not args.force and prev == cur:
            continue
        time.sleep(0.2)  # 限流

        contrib = fetch_contributors(repo) if repo else 0
        dep_cnt, dep_off = fetch_deps(repo, pkg)
        p["contributors"] = contrib
        p["depCount"] = dep_cnt
        p["depsOfficial"] = dep_off
        p["repoOwner"] = repo.split("/")[0] if repo else (pkg.split("/")[0].lstrip("@") if "/" in pkg else "")
        p["_enriched"] = cur

        md = fetch_readme(repo, pkg)
        if md:
            branch = detect_branch(repo) if repo else "main"
            readmes[p["slug"]] = {"html": to_html(md, repo, branch), "updatedAt": p.get("updated", "")}
        done += 1
        print(f"[{args.start + i}/{total}] {name}: contrib={contrib} deps={dep_cnt} official={dep_off} readme={len(md)}")

    json.dump(db, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(readmes, open(README_OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"done: {done} plugins enriched, readmes={len(readmes)}")


if __name__ == "__main__":
    main()
