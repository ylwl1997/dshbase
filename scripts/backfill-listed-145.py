#!/usr/bin/env python3
"""One-off backfill: undo the #145 "always verified" default.

#145 (e436bea, 2026-10-14) made ingest / dsh.so sync write test="verified" for
every new row and flipped 12 issue-ingest rows pending -> verified with a
stamped testDate of 2026-10-14, without running any install test.

This script compares src/data/plugins.json against the catalog as it was
right before #145 (git e436bea^) by canonical GitHub owner/repo:

  * a row that was already `verified` before #145      -> untouched (tested history)
  * a row that is `verified` now but was not verified
    (or did not exist) before #145, and whose note has
    no real test evidence (PASS / verified on dsh / 验证: ok / 通过) -> test="listed",
    and the outward-only testDate is dropped.

Usage: python3 scripts/backfill-listed-145.py [--dry-run]
"""
import json
import re
import subprocess
import sys

DATA = "src/data/plugins.json"
BASE_REV = "e436bea^"
EVIDENCE = re.compile(r"\bPASS\b|verified on dsh|L[1-4][^.;；]*verified|验证:\s*ok|通过", re.I)


def canon(u):
    """Canonical GitHub owner/repo; non-GitHub URLs (e.g. npmjs.com) fall back to the URL itself."""
    m = re.search(r"github\.com/([^/\s?#]+)/([^/\s?#]+)", u or "", re.I)
    if m:
        return f"{m.group(1)}/{m.group(2).removesuffix('.git')}".lower()
    return (u or "").strip().rstrip("/").lower() or None


def main():
    dry = "--dry-run" in sys.argv
    pre = json.loads(subprocess.check_output(["git", "show", f"{BASE_REV}:{DATA}"]))
    pre_verified = {canon(p.get("url")) for it in pre.values() for p in it if p.get("test") == "verified"}
    pre_verified.discard(None)

    db = json.load(open(DATA, encoding="utf-8"))
    changed, kept_evidence = [], []
    for cat, items in db.items():
        for p in items:
            if p.get("test") != "verified":
                continue
            if canon(p.get("url")) in pre_verified:
                continue
            if EVIDENCE.search(p.get("note") or ""):
                kept_evidence.append(p["name"])
                continue
            changed.append((cat, p["name"], p.get("testDate")))
            p["test"] = "listed"
            p.pop("testDate", None)

    print(f"backfill -> listed: {len(changed)}")
    print(f"kept verified (post-#145 but note has test evidence): {len(kept_evidence)} {kept_evidence}")
    for c, n, td in changed[:20]:
        print(f"  {c}: {n} (testDate was {td})")
    if not dry:
        json.dump(db, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
