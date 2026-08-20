#!/usr/bin/env python3
"""List true L4 (web CDP) queue from plugins.json — not the old web-L3 CDP backlog.

Buckets:
  awaiting-l4  — webonly + pending, note says 待 L4 / web-only, no L4 *-fail
  l4-fail      — pending with L4 web CDP *-fail (retriable only if env was dirty)
  not-l4       — everything else pending (headless fail / old web L3 CDP fail)

Usage:
  python3 scripts/list-l4-queue.py
  python3 scripts/list-l4-queue.py --tsv /tmp/l4-awaiting.tsv   # write verify-webonly list
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "src", "data", "plugins.json")


def bucket(p: dict) -> str:
    if p.get("test") != "pending":
        return "skip"
    note = (p.get("note") or "").lower()
    webonly = bool(p.get("webonly"))
    if re.search(r"\bl4\b", note) and re.search(
        r"(runtime|load|install)[- ]fail|still web-only", note
    ):
        return "l4-fail"
    if webonly and not re.search(r"(runtime|load|install)[- ]fail|still web-only", note):
        if (
            "待 l4" in note
            or "待 web" in note
            or "web-only" in note
            or "webonly" in note
            or not note.strip()
        ):
            return "awaiting-l4"
    return "not-l4"


def src_of(p: dict) -> tuple[str, str] | None:
    if p.get("npm") and p.get("pkg"):
        return p["pkg"], "npm"
    m = re.search(r"github\.com/([^/]+/[^/]+)", p.get("url") or "", re.I)
    if not m:
        return None
    return "github:" + m.group(1).rstrip("/"), "git"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tsv", help="Write awaiting-l4 (+ optional --include-l4-fail) as verify-webonly list")
    ap.add_argument(
        "--include-l4-fail",
        action="store_true",
        help="Also include l4-fail rows in --tsv (only if you intend a clean-port retry)",
    )
    args = ap.parse_args()

    db = json.load(open(DATA, encoding="utf-8"))
    buckets: dict[str, list] = {"awaiting-l4": [], "l4-fail": [], "not-l4": []}
    for items in db.values():
        for p in items:
            b = bucket(p)
            if b == "skip":
                continue
            buckets[b].append(p)

    for b in buckets:
        buckets[b].sort(key=lambda p: int(p.get("stars") or 0), reverse=True)

    print(
        f"awaiting-l4={len(buckets['awaiting-l4'])}  "
        f"l4-fail={len(buckets['l4-fail'])}  "
        f"not-l4(pending)={len(buckets['not-l4'])}",
        file=sys.stderr,
    )
    for b in ("awaiting-l4", "l4-fail"):
        print(f"\n=== {b} ===", file=sys.stderr)
        for p in buckets[b]:
            src = src_of(p)
            src_s = src[0] if src else "?"
            print(
                f"  {int(p.get('stars') or 0):5d}  {p['name']}  {src_s}  |  {(p.get('note') or '')[:90]}",
                file=sys.stderr,
            )

    if args.tsv:
        rows = list(buckets["awaiting-l4"])
        if args.include_l4_fail:
            rows.extend(buckets["l4-fail"])
        with open(args.tsv, "w", encoding="utf-8") as f:
            for p in rows:
                src = src_of(p)
                if not src:
                    print(f"skip (no src): {p['name']}", file=sys.stderr)
                    continue
                s, kind = src
                f.write(f"{int(p.get('stars') or 0)}\t{p['name']}\t{s}\t{kind}\n")
        print(f"wrote {args.tsv} ({len(rows)} rows)", file=sys.stderr)


if __name__ == "__main__":
    main()
