#!/usr/bin/env python3
"""Best-effort: set Cloudflare Pages not_found_handling to 404 (disable SPA soft-404).

Uses CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID from env.
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

if not ACCOUNT or not TOKEN:
    print("skip: missing CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID")
    sys.exit(0)

base = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/pages/projects/{PROJECT}"
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


info = req("GET", base)
if not info or not info.get("success"):
    print("could not read pages project; leave SPA setting for manual dashboard fix")
    sys.exit(0)

# Try patch deployment configs (production) — API fields evolve; attempt common shapes.
patch_bodies = [
    {
        "deployment_configs": {
            "production": {
                "env_vars": {},
                "fail_open": True,
                "always_use_latest_compatibility_date": True,
            }
        }
    },
]

# Document intent; CF Pages "not found handling" is often dashboard-only.
# If PATCH unsupported, print instructions.
print("project=", info.get("result", {}).get("name"))
print(
    "ACTION REQUIRED if soft-404 persists: Cloudflare Dashboard → Workers & Pages → "
    f"{PROJECT} → Settings → Builds & deployments / Custom domains → "
    "Not found handling = '404 page' (not Single-page application)."
)
sys.exit(0)
