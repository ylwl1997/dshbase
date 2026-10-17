#!/usr/bin/env python3
"""Supplemental sync from GitHub topic `dsh-plugin` (hot repos only).

Product (2026-10-14): dsh.so is the primary daily source (see sync-dshso.py).
This script only ingests/refreshes especially popular topic repos.

Hot threshold (documented rule — pick one, keep stable):
  stars >= 100

Repos below the bar are skipped (printed). Already-listed plugins that meet
the threshold get stars/forks/issues/language/updated/archived refreshed.
Topic repos not in the catalog that meet the threshold are reported as
candidates (not auto-added here — listing stays curated / issue / dsh.so).
When candidates are later ingested (ingest-plugin / sync-dshso), new rows
default to test="listed"; this script only refreshes stars/meta and never
touches `test`.

Dedup identity when matching the catalog: canonical GitHub owner/repo only
(normalize https/http, www, .git, trailing slash, case). Display names alone
are never used as duplicate keys.

Usage: GITHUB_TOKEN=xxx python scripts/sync-topic.py [--dry-run]

Schedule: preferred workflow is sync-plugins.yml (see
docs/ops/sync-plugins.yml.proposed). Until that lands, the legacy
sync-topic.yml job still works: this script runs sync-dshso.py first
unless --topic-only is passed.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from datetime import date

API = "https://api.github.com"
DATA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "data", "plugins.json"))
SYNC = os.path.join(os.path.dirname(DATA), "sync-date.json")

# Hot bar: stars >= 100 (clear, stable rule for supplemental topic ingest)
HOT_STARS = 100


def canonical_repo(url_or_key: str | None) -> str | None:
    if not url_or_key:
        return None
    s = str(url_or_key).strip()
    m = re.search(
        r"(?:https?://)?(?:www\.)?github\.com/([^/\s?#]+)/([^/\s?#]+)",
        s,
        re.I,
    )
    if m:
        owner, repo = m.group(1), m.group(2)
    else:
        m = re.match(r"^([^/\s]+)/([^/\s]+)$", s)
        if not m:
            return None
        owner, repo = m.group(1), m.group(2)
    owner = owner.strip("/")
    repo = repo.removesuffix(".git").rstrip("/").strip("/")
    if not owner or not repo:
        return None
    return f"{owner}/{repo}".lower()


def gh(path: str):
    req = urllib.request.Request(
        API + path,
        headers={
            "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "User-Agent": "dshbase-sync",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def fetch_topic():
    repos = {}
    page = 1
    total = 0
    while page <= 10:
        data = gh(
            f"/search/repositories?q=topic:dsh-plugin&sort=stars&order=desc&per_page=100&page={page}"
        )
        total = data.get("total_count", 0)
        items = data.get("items", [])
        if not items:
            break
        for it in items:
            repos[it["full_name"].lower()] = it
        if len(repos) >= total:
            break
        page += 1
        time.sleep(1.2)
    return repos, total


def is_hot(it: dict) -> bool:
    return (it.get("stargazers_count") or 0) >= HOT_STARS


def maybe_run_dshso(argv: list[str]) -> None:
    """Legacy sync-topic.yml only invokes this file — run primary dsh.so sync first.

    Pass --topic-only to skip (when sync-plugins.yml already ran sync-dshso.py).
    Forwards --dry-run / --no-add / --max-add N when present.
    """
    if "--topic-only" in argv:
        return
    import runpy
    syn = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sync-dshso.py")
    saved = list(sys.argv)
    fwd = [syn]
    for flag in ("--dry-run", "--no-add"):
        if flag in argv:
            fwd.append(flag)
    # optional --max-add N
    if "--max-add" in argv:
        i = argv.index("--max-add")
        fwd.append("--max-add")
        if i + 1 < len(argv):
            fwd.append(argv[i + 1])
    print("== primary: sync-dshso.py ==")
    sys.argv = fwd
    try:
        runpy.run_path(syn, run_name="__main__")
    finally:
        sys.argv = saved
    print("== supplement: topic hot-only ==")


def main():
    dry = "--dry-run" in sys.argv
    maybe_run_dshso(sys.argv)
    repos, total = fetch_topic()
    print(f"topic:dsh-plugin total≈{total}, fetched {len(repos)} (search cap 1000)")
    print(f"hot threshold: stars >= {HOT_STARS}")

    hot = {k: v for k, v in repos.items() if is_hot(v)}
    cold = {k: v for k, v in repos.items() if not is_hot(v)}
    print(f"hot: {len(hot)}  skipped(cold): {len(cold)}")
    if cold:
        # Print a compact skip sample (lowest stars first among skipped)
        sample = sorted(cold.items(), key=lambda kv: kv[1].get("stargazers_count") or 0)[:15]
        print("  skipped sample (stars < threshold):")
        for key, it in sample:
            print(f"    skip ★{it.get('stargazers_count') or 0:<6} {key}")
        if len(cold) > 15:
            print(f"    … and {len(cold) - 15} more skipped")

    d = json.load(open(DATA, encoding="utf-8"))
    matched = updated = 0
    skipped_listed = 0

    for items in d.values():
        for p in items:
            key = canonical_repo(p.get("url"))
            if not key or key not in repos:
                continue
            it = repos[key]
            if not is_hot(it):
                skipped_listed += 1
                continue
            matched += 1
            if (
                p.get("stars") != it.get("stargazers_count")
                or p.get("forks") != it.get("forks_count")
                or p.get("issues") != it.get("open_issues_count")
                or p.get("language") != it.get("language")
                or p.get("archived") != bool(it.get("archived"))
            ):
                p["stars"] = it.get("stargazers_count") or 0
                p["forks"] = it.get("forks_count") or 0
                p["issues"] = it.get("open_issues_count") or 0
                p["language"] = it.get("language") or p.get("language")
                p["updated"] = (it.get("pushed_at") or p.get("updated") or "")[:10]
                p["archived"] = bool(it.get("archived"))
                updated += 1

    ours = {canonical_repo(p.get("url")) for items in d.values() for p in items}
    ours.discard(None)
    new_available = []
    for key, it in hot.items():
        if key not in ours and not it.get("archived") and not it.get("fork"):
            new_available.append(
                (it.get("stargazers_count") or 0, key, (it.get("description") or "")[:60])
            )
    new_available.sort(reverse=True)

    print(
        f"hot matched in catalog: {matched}  refreshed: {updated}  "
        f"listed-but-cold(skipped refresh): {skipped_listed}"
    )
    print(f"hot candidates not in catalog (top 20):")
    for stars, name, desc in new_available[:20]:
        print(f"  ★{stars:<6} {name:45} {desc}")

    if not dry and updated:
        json.dump(d, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"wrote {DATA} (updated {updated})")
    elif dry:
        print("dry-run: no writes")

    today = date.today().isoformat()
    if not dry:
        # Do not clobber sync-date if dsh.so step already set today; still stamp
        json.dump({"updated": today}, open(SYNC, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"wrote {SYNC} updated={today}")


if __name__ == "__main__":
    main()
