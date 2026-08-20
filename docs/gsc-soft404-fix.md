# Cloudflare Pages soft-404 (SPA fallback)

## Symptom
Deleted plugin URLs (e.g. `/plugins/LiuHe/`) returned **HTTP 200 + homepage HTML** with `canonical` → `/`.
Google Search Console then reported them as **Excluded by noindex** / **Alternate with proper canonical** (~64+27).

## Fix in this repo
1. `src/pages/404.astro` — real 404 page with `noindex`.
2. `public/_redirects` — 301 known deleted plugin paths → `/plugins/directory/`.
3. Disable SPA not-found handling in Cloudflare (required for unknown paths):

**Dashboard:** Workers & Pages → **dshbase** → Settings → **Not found handling** → choose **404 page** (not “Single-page application”).

After deploy, spot-check:
```bash
curl -sI https://dshbase.com/this-page-definitely-missing-xyz/
# expect: HTTP/2 404  (and body from 404.html)
curl -sI https://dshbase.com/plugins/LiuHe/
# expect: HTTP/2 301 → /plugins/directory/
```

Then in GSC → Pages → “Excluded by noindex” → **Validate fix**.
