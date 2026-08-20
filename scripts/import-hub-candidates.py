#!/usr/bin/env python3
"""Import Hub catalog clues into dshbase as pending (never auto-verified).

Hub's installability=verified is a *candidate* signal only. This script:
  1. Fetches https://dsh-hub.cc/api/v1/plugins (scope=verified by default)
  2. Diffs against src/data/plugins.json by GitHub repo
  3. Prints / optionally ingests missing repos with test=pending

Usage:
  python scripts/import-hub-candidates.py              # dry-run top gaps
  python scripts/import-hub-candidates.py --limit 50
  python scripts/import-hub-candidates.py --ingest --limit 20   # needs GITHUB_TOKEN

Never marks entries verified — that requires L1/L2/L3 on the verify host.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "data" / "plugins.json"
HUB = "https://dsh-hub.cc/api/v1/plugins"


def fetch_hub(scope: str, limit: int, offset: int = 0) -> dict:
    url = f"{HUB}?scope={scope}&limit={limit}&offset={offset}&sort=stars"
    req = urllib.request.Request(
        url, headers={"User-Agent": "dshbase-hub-import", "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_hub_pages(scope: str, max_items: int) -> list:
    items = []
    offset = 0
    page = min(100, max_items)
    while len(items) < max_items:
        d = fetch_hub(scope, page, offset)
        batch = d.get("items") or []
        if not batch:
            break
        items.extend(batch)
        offset += len(batch)
        if offset >= int(d.get("total") or 0):
            break
    return items[:max_items]


def parse_repo(url: str | None) -> str | None:
    m = re.search(r"github\.com/([^/\s]+)/([^/\s#?]+)", url or "", re.I)
    if not m:
        return None
    return f"{m.group(1)}/{m.group(2)}".removesuffix(".git").lower()


def known_repos(db: dict) -> set[str]:
    out = set()
    for items in db.values():
        for p in items:
            r = parse_repo(p.get("url"))
            if r:
                out.add(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", default="verified", choices=["verified", "unverified", "all"])
    ap.add_argument("--scan", type=int, default=400, help="How many Hub rows to scan (by stars)")
    ap.add_argument("--limit", type=int, default=50, help="Max missing candidates to report/ingest")
    ap.add_argument("--min-stars", type=int, default=5)
    ap.add_argument("--min-confirmed", type=int, default=0, help="Hub confirmedInstallCount floor")
    ap.add_argument("--ingest", action="store_true", help="Call ingest-plugin.py for each gap")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    db = json.loads(DATA.read_text(encoding="utf-8"))
    known = known_repos(db)
    hub_items = fetch_hub_pages(args.scope, args.scan)

    gaps = []
    for it in hub_items:
        repo = parse_repo(it.get("repositoryUrl") or f"https://github.com/{it.get('fullName')}")
        if not repo:
            continue
        if repo in known:
            continue
        stars = int(it.get("stars") or 0)
        confirmed = int(it.get("confirmedInstallCount") or 0)
        if stars < args.min_stars:
            continue
        if confirmed < args.min_confirmed:
            continue
        # skip obvious non-plugins from unverified bucket
        if (it.get("installability") or "") == "unsupported":
            continue
        gaps.append(
            {
                "repo": repo,
                "name": it.get("name") or repo.split("/")[-1],
                "stars": stars,
                "confirmedInstallCount": confirmed,
                "hub_installability": it.get("installability"),
                "url": f"https://github.com/{repo}",
                "category_hint": it.get("category") or "",
            }
        )
        if len(gaps) >= args.limit:
            break

    summary = {
        "hub_scanned": len(hub_items),
        "known_repos": len(known),
        "gaps": len(gaps),
        "note": "Hub installability is a clue only; ingest writes test=pending. L3 must run separately.",
        "candidates": gaps,
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Hub scanned={len(hub_items)} known={len(known)} gaps={len(gaps)} (scope={args.scope})")
        for g in gaps:
            print(
                f"  {g['stars']:5d}★  conf={g['confirmedInstallCount']:3d}  "
                f"{g['repo']}  [{g['hub_installability']}]"
            )

    if not args.ingest:
        return 0

    if not os.environ.get("GITHUB_TOKEN"):
        print("ERROR: GITHUB_TOKEN required for --ingest", file=sys.stderr)
        return 1

    ingest = ROOT / "scripts" / "ingest-plugin.py"
    ok = fail = 0
    for g in gaps:
        cmd = [
            sys.executable,
            str(ingest),
            g["url"],
            "--force",
            "--json",
        ]
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=180)
        line = (r.stdout or r.stderr or "").strip().splitlines()
        last = line[-1] if line else f"exit={r.returncode}"
        print(f"INGEST {g['repo']}: {last[:200]}")
        if r.returncode == 0:
            ok += 1
        else:
            fail += 1
    print(f"Done ingest ok={ok} fail={fail}. All new entries are pending — run verify-runtime.sh next.")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main() or 0)
