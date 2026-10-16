#!/usr/bin/env python3
"""Best-effort: remind to disable SPA soft-404 + purge stale on-demand plugin URLs.

Uses CLOUDFLARE_API_TOKEN (+ optional CLOUDFLARE_ACCOUNT_ID) from env.
Safe to no-op if token lacks permission or API shape differs.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

ACCOUNT = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
PROJECT = os.environ.get("CF_PAGES_PROJECT", "dshbase")

if not TOKEN:
    print("skip: missing CLOUDFLARE_API_TOKEN")
    sys.exit(0)

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "dshbase-cf-404-fix",
}


def req(method: str, url: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", "replace")
        print(f"HTTP {e.code}: {err[:800]}")
        return None


# Soft-404 reminder needs account id; purge below only needs zone + token.
if ACCOUNT:
    base = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/pages/projects/{PROJECT}"
    info = req("GET", base)
    if info and info.get("success"):
        print("project=", info.get("result", {}).get("name"))
    else:
        print("could not read pages project; leave SPA setting for manual dashboard fix")
    print(
        "ACTION REQUIRED if soft-404 persists: Cloudflare Dashboard → Workers & Pages → "
        f"{PROJECT} → Settings → Builds & deployments / Custom domains → "
        "Not found handling = '404 page' (not Single-page application)."
    )
else:
    print("skip pages project check: missing CLOUDFLARE_ACCOUNT_ID (purge still runs)")

# Purge stale edge responses for on-demand plugin pages (long s-maxage can outlive deploys).
# #150 removed googlebot noindex from Functions, but custom-domain edge bodies with
# X-Robots-Tag: noindex / googlebot meta can linger until purged (seo-dash #3196).
#
# NOTE: GitHub/box CLOUDFLARE_API_TOKEN currently lacks Cache Purge (purge returns 401).
# Fallback already live in CF: Worker `dshbase-beauticode-cachebust` proxies matching
# custom-domain paths to https://dshbase.pages.dev and strips X-Robots-Tag. Routes:
#   dshbase.com|www /zh/plugins/{beautiCode,custom-first-control-prompt,dsh-omi-voice}*
# Zone cache rule also bypasses cache for /zh/plugins/* (except directory).
# Prefer fixing token Cache Purge + this PURGE_FILES list; keep Worker routes as belt-and-suspenders.
PURGE_FILES = [
    "https://dshbase.com/zh/plugins/beautiCode/",
    "https://www.dshbase.com/zh/plugins/beautiCode/",
    "https://dshbase.com/plugins/beautiCode/",
    "https://dshbase.com/zh/plugins/agent-skills-2/",
    "https://dshbase.com/zh/plugins/causal-memory/",
    "https://dshbase.com/zh/plugins/custom-first-control-prompt/",
    "https://www.dshbase.com/zh/plugins/custom-first-control-prompt/",
    "https://dshbase.com/plugins/custom-first-control-prompt/",
    "https://dshbase.com/zh/plugins/dsh-omi-voice/",
    "https://www.dshbase.com/zh/plugins/dsh-omi-voice/",
    "https://dshbase.com/plugins/dsh-omi-voice/",
]
zone_list = req("GET", "https://api.cloudflare.com/client/v4/zones?name=dshbase.com")
zone_id = None
if zone_list and zone_list.get("success") and zone_list.get("result"):
    zone_id = zone_list["result"][0].get("id")
if not zone_id:
    print("purge skip: could not resolve dshbase.com zone id")
    sys.exit(0)
purge_resp = req(
    "POST",
    f"https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache",
    {"files": PURGE_FILES},
)
if purge_resp and purge_resp.get("success"):
    print("purge ok:", len(PURGE_FILES), "files")
else:
    print("purge failed:", json.dumps((purge_resp or {}).get("errors", purge_resp), ensure_ascii=False)[:500])
sys.exit(0)
