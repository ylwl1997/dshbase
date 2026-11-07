#!/usr/bin/env python3
"""Daily primary sync: pull plugin catalog metadata from dsh.so into plugins.json.

Product (2026-10-14): dsh.so is the primary daily source; GitHub topic `dsh-plugin`
is supplemental only (see sync-topic.py). We do not re-screen the upstream feed.
New catalog rows are written with test="listed" (metadata only — dshbase has not
install-tested them; compat-check / verify-runtime promote to verified on a real
pass). Refresh never touches `test` (do not downgrade existing verified entries).

Source: https://www.dsh.so/search-index.json
  (includes owner/repo — no detail-page scrape required for cron)

  Current payload is a v2 object {v, d, i, p}:
    v = 2
    d.c  category names; d.u  use-case names
    i    rows [slug, name, owner, repo, description,
               cat_indices, usecase_indices, stars_str, starsN]
    p    topic cards — ignored
  load_index() expands each i row into a dict with
  name, owner, repo, description, stars, starsN, ucs, categories, slug.
  A legacy JSON array of those objects is still accepted.
  Malformed rows are skipped. SKIP_NAMES (deepseek-harness) is always
  dropped. Upstream category "Interface & Layout" folds into "UI & Skins".
  Catalog rows are not stamped with a public source attribution.

Dedup identity: canonical GitHub owner/repo only
  (normalize https/http, www, .git suffix, trailing slash, case).
  Display-name collisions alone are NOT duplicates.
  When two index rows share a repo, the higher starsN wins.

Usage:
  python scripts/sync-dshso.py [--dry-run] [--no-add] [--max-add N]
                               [--index PATH] [--timeout SEC]

Flags:
  --dry-run   print plan; do not write plugins.json / sync-date.json
  --no-add    refresh matched repos only; do not append new entries
  --max-add N cap how many new repos to append (smoke / first-run throttle)
  --index PATH  use a local search-index.json instead of fetching
  --timeout SEC HTTP timeout for the index fetch (default 120)

CI: .github/workflows/sync-plugins.yml runs this daily ~04:17 UTC, then the
topic supplement, then gen-repos / gen-sitemap / gen-badges / enrich steps.

First production sync may add a large delta of new dsh.so repos; that is
intentional and idempotent. Prefer letting the scheduled job commit data
rather than baking a one-shot mega diff into a code PR.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import date

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB = os.path.join(ROOT, "src", "data", "plugins.json")
SYNC = os.path.join(ROOT, "src", "data", "sync-date.json")
INDEX_URL = "https://www.dsh.so/search-index.json"
UA = {
    "User-Agent": "dshbase-sync-dshso/1.0 (+https://github.com/ylwl1997/dshbase)"
}

# Catalog buckets. key=ours, value=upstream names that fold into the key.
# "Interface & Layout" is the v2 label for the UI bucket.
CAT_MERGE = {
    "Developer": ["Developer"],
    "AI Models": ["AI Models"],
    "UI & Skins": ["UI & Skins", "Game", "Interface & Layout"],
    "Knowledge": ["Knowledge"],
    "Desktop": ["Desktop", "Launcher"],
    "Automation": ["Automation"],
    "Network": ["Network"],
    "Browser": ["Browser"],
    "Terminal": ["Terminal"],
    "Storage": ["Storage"],
    "Vision": ["Vision"],
    "Data": ["Data", "Finance"],
    "Security": ["Security"],
    "Productivity": ["Productivity"],
    "Content": ["Content", "Media"],
}
THEIR_CAT_TO_NEW = {s: new for new, srcs in CAT_MERGE.items() for s in srcs}

USE_CASES = [
    "Terminal / Shell",
    "File",
    "Vision / OCR",
    "Memory",
    "Database",
    "Web search",
    "Storage",
    "GitHub integration",
    "Code review",
    "Notifications",
    # v2 d.u names that were not in the original allow-list
    "Agent orchestration",
    "Creator & social",
    "Office automation",
    "Skins & Themes",
]

SKIP_NAMES = {"deepseek-harness"}


def canonical_repo(url_or_key: str | None) -> str | None:
    """Normalize to lowercase 'owner/repo'. URLs and bare owner/repo accepted.

    Same GitHub repository identity only — not display name.
    """
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
    if not owner or not repo or "/" in owner:
        return None
    return f"{owner}/{repo}".lower()


def http_get(url: str, timeout: int = 120) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_stars(s) -> int:
    if s is None:
        return 0
    if isinstance(s, (int, float)):
        return int(s)
    s = str(s).strip().lower().replace(",", "")
    m = re.match(r"([\d.]+)\s*([km]?)", s)
    if not m:
        return 0
    v = float(m.group(1))
    unit = m.group(2)
    if unit == "k":
        v *= 1000
    elif unit == "m":
        v *= 1_000_000
    return int(v)


def stars_of(item: dict) -> int:
    if item.get("starsN") is not None:
        try:
            return int(item["starsN"])
        except (TypeError, ValueError):
            pass
    return parse_stars(item.get("stars"))


def primary_cat(cats: list) -> str:
    for c in cats:
        mapped = THEIR_CAT_TO_NEW.get(c)
        if mapped:
            return mapped
    return "Developer"


def meta_categories(meta: dict) -> list:
    """Category names for a row. v2 uses `categories`; legacy objects used `cats`."""
    cats = meta.get("categories")
    if isinstance(cats, list) and cats:
        return cats
    legacy = meta.get("cats")
    return legacy if isinstance(legacy, list) else []


def make_slug(name: str, fallback: str) -> str:
    if fallback:
        return fallback
    if name.startswith("@"):
        return name.lstrip("@").replace("/", "-")
    return name


def _text(value) -> str:
    """Coerce a scalar index field to a stripped string. Containers become empty."""
    if isinstance(value, str):
        return value.strip()
    if value is None or isinstance(value, (list, dict, bool)):
        return ""
    return str(value).strip()


def _coerce_stars_n(stars_n, stars) -> int:
    if isinstance(stars_n, bool):
        return parse_stars(stars)
    if isinstance(stars_n, int):
        return stars_n
    if isinstance(stars_n, float):
        return int(stars_n)
    parsed = parse_stars(stars_n)
    if parsed:
        return parsed
    return parse_stars(stars)


def _lookup_names(table, indices) -> list | None:
    """Resolve a list of indexes into table names.

    None means the index field itself is malformed (not a list). Out-of-range
    or non-int indexes are dropped so one bad pointer does not discard the row.
    """
    if not isinstance(indices, list):
        return None
    if not isinstance(table, list):
        table = []
    names: list[str] = []
    for i in indices:
        # bool is an int subclass; True would otherwise select table[1].
        if isinstance(i, bool) or not isinstance(i, int):
            continue
        if 0 <= i < len(table) and isinstance(table[i], str) and table[i]:
            names.append(table[i])
    return names


def _expand_v2_row(row, cat_names: list, uc_names: list) -> dict | None:
    """Expand one v2 `i` row into the dict shape the rest of the sync expects.

    Row layout: [slug, name, owner, repo, description, cat_indices,
    usecase_indices, stars_str, starsN]. Returns None for a bad row.
    """
    if not isinstance(row, (list, tuple)) or len(row) < 9:
        return None
    slug, name, owner, repo, description, cat_idx, uc_idx, stars, stars_n = row[:9]
    name_s = _text(name)
    if not name_s:
        return None
    categories = _lookup_names(cat_names, cat_idx)
    usecases = _lookup_names(uc_names, uc_idx)
    if categories is None or usecases is None:
        return None
    return {
        "slug": _text(slug),
        "name": name_s,
        "owner": _text(owner),
        "repo": _text(repo),
        "description": _text(description),
        "stars": stars if isinstance(stars, str) else _text(stars),
        "starsN": _coerce_stars_n(stars_n, stars),
        "ucs": usecases,
        "categories": categories,
    }


def _load_v2(raw: dict) -> list:
    """Expand a {v, d, i, p} document. `p` (topic cards) is intentionally unused."""
    d = raw.get("d") if isinstance(raw.get("d"), dict) else {}
    cat_names = d.get("c") if isinstance(d.get("c"), list) else []
    uc_names = d.get("u") if isinstance(d.get("u"), list) else []
    out = []
    skipped = 0
    for row in raw.get("i") or []:
        item = _expand_v2_row(row, cat_names, uc_names)
        if item is None:
            skipped += 1
            continue
        if item["name"] in SKIP_NAMES:
            continue
        out.append(item)
    if skipped:
        print(f"search-index: skipped {skipped} bad rows")
    return out


def _load_legacy_array(raw: list) -> list:
    """Accept the pre-v2 JSON array of plugin objects. Non-objects are bad rows."""
    out = []
    skipped = 0
    for x in raw:
        if not isinstance(x, dict):
            skipped += 1
            continue
        if x.get("name") in SKIP_NAMES:
            continue
        # Older objects used `cats`. Downstream reads `categories`.
        if "categories" not in x and isinstance(x.get("cats"), list):
            x = {**x, "categories": list(x["cats"])}
        out.append(x)
    if skipped:
        print(f"search-index: skipped {skipped} bad rows")
    return out


def load_index(path: str | None, timeout: int) -> list:
    """Load the upstream search index as a list of plugin dicts.

    Supports the current v2 object and a legacy JSON array of objects.
    """
    if path:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    else:
        raw = json.loads(http_get(INDEX_URL, timeout=timeout))
    if isinstance(raw, list):
        return _load_legacy_array(raw)
    if isinstance(raw, dict) and raw.get("v", 2) == 2 and isinstance(raw.get("i"), list):
        return _load_v2(raw)
    raise SystemExit(
        "search-index.json: expected a v2 object {v, d, i, p} or a legacy array"
    )


def index_by_repo(their: list) -> dict:
    """Map canonical repo -> best index row (highest starsN wins on collision)."""
    by: dict[str, dict] = {}
    for x in their:
        owner, repo = x.get("owner") or "", x.get("repo") or ""
        key = canonical_repo(f"{owner}/{repo}") if owner and repo else None
        if not key:
            continue
        prev = by.get(key)
        if prev is None or stars_of(x) > stars_of(prev):
            by[key] = x
    return by


def ensure_cats(db: dict) -> None:
    for c in CAT_MERGE:
        db.setdefault(c, [])


def refresh_plugin(p: dict, meta: dict) -> bool:
    """Update mutable fields from dsh.so. Never touch `test` (never downgrade verified)."""
    changed = False
    stars = stars_of(meta)
    if p.get("stars") != stars:
        p["stars"] = stars
        changed = True
    trust = meta.get("trust") or p.get("trust") or "Unrated"
    if p.get("trust") != trust:
        p["trust"] = trust
        changed = True
    ucs = [u for u in (meta.get("ucs") or []) if u in USE_CASES]
    if ucs and p.get("ucs") != ucs:
        p["ucs"] = ucs
        changed = True
    # v2 rows have no health field. Absence must not clear an existing flag.
    if "health" in meta:
        archived = meta.get("health") == "Archived"
        if bool(p.get("archived")) != archived:
            p["archived"] = archived
            changed = True
    # Prefer dsh.so description when ours is empty
    desc = (meta.get("description") or "").strip()
    if desc:
        if not (p.get("desc") or "").strip():
            p["desc"] = desc
            changed = True
        if not (p.get("desc_en") or "").strip():
            p["desc_en"] = desc
            changed = True
    p.setdefault("license", "")
    p.setdefault("ucs", [])
    p.setdefault("trust", "Unrated")
    return changed


def build_new_entry(meta: dict, today: str) -> dict:
    owner, repo = meta["owner"], meta["repo"]
    key = canonical_repo(f"{owner}/{repo}")
    name = meta.get("name") or repo
    slug = make_slug(name, meta.get("slug") or "")
    return {
        "name": name,
        "url": f"https://github.com/{key}",
        "pkg": "",
        "ver": "",
        "npm": False,
        "test": "listed",  # metadata-only; verified only after a real install test
        "desc": meta.get("description") or "",
        "desc_en": meta.get("description") or "",
        "desc_zh": "",
        "stars": stars_of(meta),
        "forks": 0,
        "issues": 0,
        "language": "",
        "updated": "",
        "archived": meta.get("health") == "Archived",
        "added": today,
        "license": "",
        "ucs": [u for u in (meta.get("ucs") or []) if u in USE_CASES],
        "trust": meta.get("trust") or "Unrated",
        "slug": slug,
        "platform": "any",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-add", action="store_true", help="refresh only; do not append new repos")
    ap.add_argument("--max-add", type=int, default=0, help="cap new adds (0 = unlimited)")
    ap.add_argument("--index", default="", help="local search-index.json path")
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args()

    their = load_index(args.index or None, args.timeout)
    by_repo = index_by_repo(their)
    print(f"dsh.so index: {len(their)} rows, {len(by_repo)} unique repos")

    db = json.load(open(DB, encoding="utf-8"))
    ensure_cats(db)

    # Index our catalog by canonical repo (first wins; name is NOT a key)
    ours_by_repo: dict[str, dict] = {}
    orphan = 0
    for items in db.values():
        for p in items:
            key = canonical_repo(p.get("url"))
            if not key:
                orphan += 1
                continue
            ours_by_repo.setdefault(key, p)

    matched = refreshed = 0
    for key, p in ours_by_repo.items():
        meta = by_repo.get(key)
        if not meta:
            continue
        matched += 1
        if refresh_plugin(p, meta):
            refreshed += 1

    missing_keys = [k for k in by_repo if k not in ours_by_repo]
    # Prefer higher-star new repos first when capped
    missing_keys.sort(key=lambda k: -stars_of(by_repo[k]))

    to_add = []
    if not args.no_add:
        limit = args.max_add if args.max_add > 0 else len(missing_keys)
        for key in missing_keys[:limit]:
            to_add.append((key, by_repo[key]))

    print(
        f"catalog repos: {len(ours_by_repo)}  matched: {matched}  "
        f"refreshed: {refreshed}  orphan(no github url): {orphan}"
    )
    print(
        f"dsh.so repos not in catalog: {len(missing_keys)}  "
        f"will add: {len(to_add)}" + (" [dry-run]" if args.dry_run else "")
    )
    if to_add[:5]:
        print("  add sample:")
        for key, meta in to_add[:5]:
            print(f"    ★{stars_of(meta):<7} {key:45} {meta.get('name')}")

    today = date.today().isoformat()
    if args.dry_run:
        print("[dry-run] no writes")
        return 0

    for key, meta in to_add:
        cat = primary_cat(meta_categories(meta))
        entry = build_new_entry(meta, today)
        # Re-check identity only (another add in this run)
        if canonical_repo(entry["url"]) in ours_by_repo:
            continue
        db.setdefault(cat, []).append(entry)
        ours_by_repo[canonical_repo(entry["url"])] = entry

    json.dump(db, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"updated": today}, open(SYNC, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    total = sum(len(v) for v in db.values())
    print(f"wrote {DB} (total entries={total}) and {SYNC} updated={today}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
