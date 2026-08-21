#!/usr/bin/env python3
"""从 dshbase 的 plugins.json 生成 dshbase-catalog 的 catalog.json。"""
import json
import os
from datetime import date

DB = os.path.join(os.path.dirname(__file__), "..", "src", "data", "plugins.json")
OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dshbase-catalog", "src", "catalog.json"))
# 允许命令行指定输出
if len(os.sys.argv) > 1:
    OUT = os.path.abspath(os.sys.argv[1])

PACKS = os.path.join(os.path.dirname(__file__), "..", "src", "data", "packs.json")


def owner_repo(url):
    return (url or "").replace("https://github.com/", "").rstrip("/")

d = json.load(open(DB, encoding="utf-8"))
plugins = []
slug_map = {}
for cat, items in d.items():
    for p in items:
        repo = owner_repo(p.get("url"))
        install = f"dsh plugin add {p['pkg']}" if (p.get("npm") and p.get("pkg")) else f"dsh plugin add github:{repo}"
        row = {
            "name": p["name"],
            "slug": p.get("slug") or p["name"],
            "category": cat,
            "url": p.get("url") or "",
            "pkg": p.get("pkg") or "",
            "npm": bool(p.get("npm")),
            "test": p.get("test") or "pending",
            "note": p.get("note") or "",
            "testDate": p.get("testDate") or "",
            "platform": p.get("platform") or "any",
            "desc": p.get("desc_en") or p.get("desc") or "",
            "desc_zh": p.get("desc_zh") or "",
            "stars": p.get("stars") or 0,
            "install": install,
            "added": p.get("added") or "",
        }
        plugins.append(row)
        slug_map[row["slug"]] = row

plugins.sort(key=lambda x: -(x["stars"] or 0))

packs_out = []
if os.path.exists(PACKS):
    packs = json.load(open(PACKS, encoding="utf-8"))
    for pack in packs.get("packs", []):
        slots = []
        for s in pack.get("slots", []):
            row = slug_map.get(s.get("slug"))
            if not row or row.get("test") != "verified":
                continue
            slots.append({
                "id": s.get("id"),
                "label_en": s.get("label_en"),
                "label_zh": s.get("label_zh"),
                "name": row["name"],
                "slug": row["slug"],
                "install": row["install"],
                "test": "verified",
            })
        if slots:
            packs_out.append({
                "id": pack["id"],
                "title_en": pack.get("title_en"),
                "title_zh": pack.get("title_zh"),
                "desc_en": pack.get("desc_en"),
                "desc_zh": pack.get("desc_zh"),
                "slots": slots,
            })

out = {
    "schema_version": 3,
    "updated": date.today().isoformat(),
    "count": len(plugins),
    "verified_definition": (
        "L1 install + L2 load + L3 runtime Q&A on dsh 0.1.0-rc.8 "
        "(not topic count / manifest-only installability)"
    ),
    "plugins": plugins,
    "packs": packs_out,
}
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"生成 catalog.json: {len(plugins)} 个插件, {len(packs_out)} 个场景包 -> {OUT}")
