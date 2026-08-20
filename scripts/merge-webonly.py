#!/usr/bin/env python3
"""合并 webonly 验证结果写回 plugins.json。

用法:
  python scripts/merge-webonly.py <results.tsv>

判定（与 verify-runtime 的 merge-verify.py 口径一致）:
  ok           -> test=verified + testDate + webonly=False
  runtime-fail -> 保持 pending，note 追加 web L3 runtime-fail（可能需外部服务/账号）
  load-fail    -> 保持 pending，note 追加 web load-fail
  install-fail -> 保持 pending，note 追加 web install-fail（git 源可能不存在/改名）
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
                    if "web-only" in low or "webonly" in low or "待 web" in part or "headless" in low:
                        continue
                    if "web l3" in low:
                        continue
                    keep.append(part)
                add = "Web L3 verified on dsh 0.1.0-rc.6 (CDP browser E2E)."
                p["note"] = ("；".join(keep) + "；" + add) if keep else add
                updated["ok"] += 1
            elif st == "web-only":
                # 装+载通过，headless 缺 GUI 服务（web/全运行时插件）——不算失败
                p["test"] = "pending"
                p["webonly"] = True
                note = p.get("note", "")
                add = "web L3 web-only on dsh 0.1.0-rc.6 (headless lacks GUI service, needs web runtime)."
                p["note"] = note + "\n" + add if note else add
                updated["web-only"] = updated.get("web-only", 0) + 1
            else:
                p["test"] = "pending"
                note = p.get("note", "")
                add = f"web L3 {st} on dsh 0.1.0-rc.6 (CDP E2E)."
                p["note"] = note + "\n" + add if note else add
                updated[st] = updated.get(st, 0) + 1

    json.dump(db, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(updated, ensure_ascii=False))
    if not_found:
        print("not found in db:", not_found)


if __name__ == "__main__":
    main()
