import urllib.request, json, ssl
# Try Cursor download API patterns
urls = [
    "https://www.cursor.com/api/download?platform=linux-x64&releaseTrack=stable",
    "https://api2.cursor.sh/updates/download?platform=linux-x64&releaseTrack=stable",
    "https://downloader.cursor.sh/linux/appImage/x64",
    "https://cursor.com/download/linux/x64",
]
ctx = ssl.create_default_context()
for u in urls:
    try:
        req = urllib.request.Request(u, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            print("HEAD", u, "->", r.status, r.geturl())
            print("  content-type:", r.headers.get("Content-Type"))
            print("  content-length:", r.headers.get("Content-Length"))
            print("  content-disposition:", r.headers.get("Content-Disposition"))
    except Exception as e:
        print("HEAD fail", u, type(e).__name__, e)

print("--- GET api ---")
for u in [
    "https://www.cursor.com/api/download?platform=linux-x64&releaseTrack=stable",
    "https://api2.cursor.sh/updates/download?platform=linux-x64&releaseTrack=stable",
]:
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            data = r.read(2000)
            print(u, "->", r.status, r.geturl())
            print(data[:1500])
    except Exception as e:
        print("GET fail", u, type(e).__name__, e)
