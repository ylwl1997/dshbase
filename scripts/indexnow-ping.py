#!/usr/bin/env python3
"""IndexNow ping (run after the site is deployed).

Reads the live sitemap (sitemap index supported), verifies the hosted key file
(<key>.txt at the site root) is live, then POSTs the URLs to api.indexnow.org.
The key is discovered from the key file shipped in KEY_DIR; it is never printed.
Usage (after a deploy is live): python3 scripts/indexnow-ping.py
"""
import json, os, re, sys, time, urllib.error, urllib.request

HOST = "dshbase.com"
SITEMAP = "https://dshbase.com/sitemap-index.xml"
KEY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public")
ENDPOINT = "https://api.indexnow.org/indexnow"
UA = {"User-Agent": "indexnow-ping/1.0 (+https://%s/)" % HOST}


def find_key():
    for name in os.listdir(KEY_DIR):
        m = re.fullmatch(r"([0-9a-f]{32})\.txt", name)
        if m and open(os.path.join(KEY_DIR, name)).read().strip() == m.group(1):
            return m.group(1)
    sys.exit("IndexNow: no key file found, skipping")


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.status, r.read().decode("utf-8", "replace")


def sitemap_urls(url):
    _, body = get(url)
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body)
    if "<sitemapindex" in body:
        out = []
        for sm in locs:
            out += sitemap_urls(sm)
        return out
    return locs


def main():
    key = find_key()
    key_url = f"https://{HOST}/{key}.txt"
    for attempt in range(10):  # wait for the deploy to be live at the edge
        try:
            st, body = get(key_url + f"?cb={int(time.time())}")
            if st == 200 and body.strip() == key:
                break
        except Exception:
            pass
        time.sleep(15)
    else:
        sys.exit("IndexNow: key file not live yet, skipping")
    print("IndexNow: key file live (HTTP 200, content matches)")
    urls = [u for u in sitemap_urls(SITEMAP) if u.startswith(f"https://{HOST}/")]
    print(f"IndexNow: {len(urls)} URLs from {SITEMAP}")
    if not urls:
        return
    for i in range(0, len(urls), 10000):
        batch = urls[i:i + 10000]
        data = json.dumps({"host": HOST, "key": key, "keyLocation": key_url, "urlList": batch}).encode()
        req = urllib.request.Request(ENDPOINT, data=data, headers={"Content-Type": "application/json; charset=utf-8", **UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                print(f"IndexNow: submitted {len(batch)} URLs -> HTTP {r.status}")
        except urllib.error.HTTPError as e:
            print(f"IndexNow: HTTP {e.code} {e.read().decode('utf-8', 'replace')[:200]}")
            if e.code not in (200, 202):
                sys.exit(1)


if __name__ == "__main__":
    main()
