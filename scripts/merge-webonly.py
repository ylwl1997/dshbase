#!/usr/bin/env python3
"""合并 L4（web CDP / verify-webonly.sh）结果写回 plugins.json。

L4 是 web-only 插件的必经关：L3 headless 标 web-only 后，只有本脚本合并 ok 才 verified。

用法:
  python scripts/merge-webonly.py <results.tsv>

判定:
  ok           -> test=verified + testDate（L4 通过）
  runtime-fail -> pending，note 追加 L4 runtime-fail
  load-fail    -> pending，note 追加 L4 load-fail
  install-fail -> pending，note 追加 L4 install-fail
"""
import json
import os
import re
import sys

DATA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "data", "plugins.json"))


def main():
    results_file = sys.argv[1] if len(sys.argv) > 1 else None
    if not results_file or not os.path.exists(results_file):
        print(f"results file not found: {results_file}")
        sys.exit(1)

    status = {}
    for line in open(results_file, encoding="utf-8"):
        line = line.strip()
        if not line or "\t" not in line:
            continue
        name, st = line.split("\t", 1)
        if name.startswith("["):   # 过滤误入的 log 行
            continue
        status[name] = st

    db = json.load(open(DATA, encoding="utf-8"))
    updated = {"ok": 0, "runtime-fail": 0, "load-fail": 0, "install-fail": 0}
    not_found = []

    for cat, items in db.items():
        for p in items:
            name = p.get("name")
            if name not in status:
                continue
            st = status[name]
            p["webonly"] = False
            if st == "ok":
                p["test"] = "verified"
                p["testDate"] = __import__("datetime").date.today().isoformat()
                # Drop stale "待 web 运行时验证" / webonly placeholders; keep LICENSE etc.
                note = (p.get("note") or "").strip()
                keep = []
                for part in re.split(r"[；;\n]+", note):
                    part = part.strip()
                    if not part:
                        continue
                    low = part.lower()
                    if "web-only" in low or "webonly" in low or "待 web" in part or "待 l4" in low or "headless" in low:
                        continue
                    if "web l3" in low or "l4 web" in low or part.startswith("验证:"):
                        continue
                    keep.append(part)
                add = "L4 web CDP verified on dsh 0.1.0-rc.6."
                p["note"] = ("；".join(keep) + "；" + add) if keep else add
                # Keep webonly=True so catalog knows this passed via web profile, not headless-only.
                p["webonly"] = True
                updated["ok"] += 1
            elif st == "web-only":
                p["test"] = "pending"
                p["webonly"] = True
                note = p.get("note", "")
                add = "L4 still web-only on dsh 0.1.0-rc.6 (unexpected)."
                p["note"] = (note + "；" + add) if note else add
                updated["web-only"] = updated.get("web-only", 0) + 1
            else:
                p["test"] = "pending"
                p["webonly"] = True
                note = p.get("note", "")
                add = f"L4 web CDP {st} on dsh 0.1.0-rc.6."
                p["note"] = (note + "；" + add) if note else add
                updated[st] = updated.get(st, 0) + 1

    json.dump(db, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(updated, ensure_ascii=False))
    if not_found:
        print("not found in db:", not_found)


if __name__ == "__main__":
    main()
