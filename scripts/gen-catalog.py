#!/usr/bin/env python3
"""从 dshbase 的 plugins.json 生成 dshbase-catalog 的 catalog.json。"""
import json
import os
import re
from datetime import date

DB = os.path.join(os.path.dirname(__file__), "..", "src", "data", "plugins.json")
OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dshbase-catalog", "src", "catalog.json"))
# 允许命令行指定输出
if len(os.sys.argv) > 1:
    OUT = os.path.abspath(os.sys.argv[1])

def owner_repo(url):
    return (url or "").replace("https://github.com/", "").rstrip("/")

d = json.load(open(DB, encoding="utf-8"))
plugins = []
for cat, items in d.items():
    for p in items:
        repo = owner_repo(p.get("url"))
        install = f"dsh plugin add {p['pkg']}" if (p.get("npm") and p.get("pkg")) else f"dsh plugin add github:{repo}"
        plugins.append({
            "name": p["name"],
            "category": cat,
            "url": p.get("url") or "",
            "pkg": p.get("pkg") or "",
            "npm": bool(p.get("npm")),
            "test": p.get("test") or "pending",
            "platform": p.get("platform") or "any",
            "desc": p.get("desc_en") or p.get("desc") or "",
            "desc_zh": p.get("desc_zh") or "",
            "stars": p.get("stars") or 0,
            "install": install,
            "added": p.get("added") or "",
        })

plugins.sort(key=lambda x: -(x["stars"] or 0))

out = {
    "schema_version": 2,
    "updated": date.today().isoformat(),
    "count": len(plugins),
    "plugins": plugins,
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"生成 catalog.json: {len(plugins)} 个插件 -> {OUT}")
