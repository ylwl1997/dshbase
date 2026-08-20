#!/usr/bin/env python3
"""Build src/data/contributors.json from repo issues x plugins.json.

For every issue (submission) authored by a GitHub user, extract github.com
repo URLs from its title/body, match them against plugins.json `url`, and
group matched plugins by author.

Usage:
  GITHUB_TOKEN=xxx python scripts/fetch-contributors.py
  GITHUB_TOKEN=xxx python scripts/fetch-contributors.py --quiet --require bentong-chain
  GITHUB_TOKEN=xxx python scripts/fetch-contributors.py --quiet \\
      --ensure-author bentong-chain --ensure-plugin dsh-dir-tree
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "src", "data", "contributors.json")
PLUGINS = os.path.join(ROOT, "src", "data", "plugins.json")

# repo renames: old issue URL -> current catalog URL (all lowercase, keys/values must match norm())
ALIASES = {
    "github.com/wwumit/dsh-skill-hub": "github.com/wwumit/dsh-compliancehub",
    "github.com/spyqwer1/dsh-imagecraft": "github.com/spyqwer1/dsh-codex-tools",
    # monorepo submission URL → dedicated npm package repo
    "github.com/nan1010082085/dsh-plugins": "github.com/nan1010082085/dsh-plugin-ima-sync",
    "github.com/nan1010082085/dsh-plugins/tree/main/packages/ima-sync": "github.com/nan1010082085/dsh-plugin-ima-sync",
}

# Contributors who submitted via the official discussion (not the issue form).
EXTRA = [
    {
        "github": "sakikoTGW",
        "avatar": "https://avatars.githubusercontent.com/u/247183209?v=4",
        "plugins": [
            {
                "name": "pack-agent-dsh",
                "slug": "pack-agent-dsh",
                "npm": True,
                "pkg": "@sakikotgw/pack-agent-dsh",
            }
        ],
    },
    {
        "github": "weijiafu14",
        "avatar": "https://avatars.githubusercontent.com/u/17469139?v=4",
        "plugins": [{"name": "pi2dsh", "slug": "pi2dsh", "npm": True, "pkg": "pi2dsh"}],
    },
    {
        "github": "sjh9714",
        "avatar": "https://avatars.githubusercontent.com/u/163989462?v=4",
        "plugins": [
            {"name": "dsh-win32", "slug": "dsh-win32", "npm": True, "pkg": "dsh-win32"},
            {
                "name": "dsh-what-changed",
                "slug": "dsh-what-changed",
                "npm": True,
                "pkg": "dsh-what-changed",
            },
        ],
    },
]

RE = re.compile(r"github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?(?:[#/)\s]|$)", re.I)


def norm(u: str) -> str:
    u = (u or "").strip().lower()
    u = re.sub(r"^https?://", "", u)
    if u.endswith(".git"):
        u = u[:-4]
    return u.rstrip("/")


def plugin_ref(p: dict) -> dict:
    return {
        "name": p.get("name"),
        "slug": p.get("slug") or p.get("name"),
        "npm": bool(p.get("npm")),
        "pkg": p.get("pkg") or "",
    }


def gh(url: str, token: str):
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + token,
            "User-Agent": "dshbase",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def load_plugins() -> dict:
    with open(PLUGINS, encoding="utf-8") as f:
        return json.load(f)


def find_plugin(db: dict, name: str):
    name_l = (name or "").lower()
    for items in db.values():
        for p in items:
            if (p.get("name") or "").lower() == name_l:
                return p
            if (p.get("slug") or "").lower() == name_l:
                return p
    return None


def build(token: str):
    issues = []
    page = 1
    while True:
        d = gh(
            f"https://api.github.com/repos/ylwl1997/dshbase/issues?state=all&per_page=100&page={page}",
            token,
        )
        if not d:
            break
        issues.extend(d)
        if len(d) < 100:
            break
        page += 1

    db = load_plugins()
    url_map = {}
    for items in db.values():
        for p in items:
            if p.get("url"):
                url_map.setdefault(norm(p["url"]), p)

    contrib = {}  # author -> {plugin_name: plugin}
    avatars = {}
    unmatched = []
    for i in issues:
        if i.get("pull_request"):
            continue
        author = i["user"]["login"]
        avatars.setdefault(author, i["user"].get("avatar_url") or "")
        text = (i.get("title") or "") + "\n" + (i.get("body") or "")
        entry = contrib.setdefault(author, {})
        for m in RE.finditer(text):
            full = norm(f"github.com/{m.group(1)}/{m.group(2)}")
            p = url_map.get(full) or url_map.get(ALIASES.get(full, ""))
            if p:
                entry[p["name"]] = p
            else:
                unmatched.append((author, full))

    result = []
    for author, pmap in contrib.items():
        if not pmap:
            continue
        plugins = [plugin_ref(pmap[name]) for name in sorted(pmap)]
        result.append(
            {"github": author, "avatar": avatars.get(author, ""), "plugins": plugins}
        )

    existing = {c["github"]: c for c in result}
    for e in EXTRA:
        if e["github"] in existing:
            seen = {p["name"] for p in existing[e["github"]]["plugins"]}
            for p in e["plugins"]:
                if p["name"] not in seen:
                    existing[e["github"]]["plugins"].append(p)
        else:
            result.append(e)
            existing[e["github"]] = result[-1]

    return result, existing, unmatched, db, avatars


def ensure_author(
    result: list,
    existing: dict,
    db: dict,
    login: str,
    plugin_name: str,
    avatars: dict,
) -> bool:
    """Force-add author↔plugin if issue URL matching missed. Returns True if present after."""
    login = (login or "").strip()
    plugin_name = (plugin_name or "").strip()
    if not login or not plugin_name:
        return False
    p = find_plugin(db, plugin_name)
    if not p:
        print(
            f"ERROR: --ensure-plugin {plugin_name!r} not found in plugins.json",
            file=sys.stderr,
        )
        return False
    ref = plugin_ref(p)
    if login in existing:
        names = {x["name"] for x in existing[login]["plugins"]}
        if ref["name"] not in names:
            existing[login]["plugins"].append(ref)
            existing[login]["plugins"].sort(key=lambda x: (x.get("name") or "").lower())
        if not existing[login].get("avatar") and avatars.get(login):
            existing[login]["avatar"] = avatars[login]
        return True
    avatar = avatars.get(login) or f"https://github.com/{login}.png"
    entry = {"github": login, "avatar": avatar, "plugins": [ref]}
    result.append(entry)
    existing[login] = entry
    return True


def main():
    ap = argparse.ArgumentParser(description="Refresh trusted contributors from issues × catalog")
    ap.add_argument("--quiet", action="store_true", help="Do not dump full JSON to stdout")
    ap.add_argument(
        "--require",
        action="append",
        default=[],
        metavar="LOGIN",
        help="Exit 1 unless LOGIN is present with ≥1 plugin (repeatable)",
    )
    ap.add_argument(
        "--ensure-author",
        default="",
        help="If matching missed, force-add this GitHub login",
    )
    ap.add_argument(
        "--ensure-plugin",
        default="",
        help="Plugin name/slug to attach with --ensure-author (must exist in plugins.json)",
    )
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("ERROR: GITHUB_TOKEN required", file=sys.stderr)
        sys.exit(1)

    result, existing, unmatched, db, avatars = build(token)
    print(f"total issues scanned; authors with plugins={len(result)}", file=sys.stderr)

    if args.ensure_author:
        if not args.ensure_plugin:
            print("ERROR: --ensure-plugin required with --ensure-author", file=sys.stderr)
            sys.exit(1)
        ok = ensure_author(
            result, existing, db, args.ensure_author, args.ensure_plugin, avatars
        )
        if not ok:
            sys.exit(1)
        print(
            f"ensured {args.ensure_author} ↔ {args.ensure_plugin}",
            file=sys.stderr,
        )

    result.sort(key=lambda c: (-len(c["plugins"]), c["github"].lower()))

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    if not args.quiet:
        print(json.dumps(result, ensure_ascii=False, indent=1))

    print(f"\n# unmatched URLs ({len(unmatched)}):", file=sys.stderr)
    for a, u in sorted(set(unmatched)):
        print(f"  {a}  {u}", file=sys.stderr)

    by_login = {c["github"].lower(): c for c in result}
    failed = []
    for login in args.require:
        c = by_login.get(login.lower())
        if not c or not c.get("plugins"):
            failed.append(login)
        else:
            names = ", ".join(p["name"] for p in c["plugins"])
            print(f"require_ok {login}: {names}", file=sys.stderr)
    if failed:
        print(
            "ERROR: required contributor(s) missing from contributors.json: "
            + ", ".join(failed),
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"wrote {OUT} ({len(result)} contributors)", file=sys.stderr)


if __name__ == "__main__":
    main()
