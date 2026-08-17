#!/usr/bin/env python3
"""Build src/data/contributors.json from repo issues x plugins.json.

For every issue (submission) authored by a GitHub user, extract github.com
repo URLs from its title/body, match them against plugins.json `url`, and
group matched plugins by author.
"""
import os, json, re, sys, urllib.request

token = os.environ["GITHUB_TOKEN"]
ROOT = r"C:\Users\Administrator\dshbase"


def gh(url):
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + token,
        "User-Agent": "dshbase",
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


# fetch all issues
issues = []
page = 1
while True:
    d = gh(f"https://api.github.com/repos/ylwl1997/dshbase/issues?state=all&per_page=100&page={page}")
    if not d:
        break
    issues.extend(d)
    if len(d) < 100:
        break
    page += 1
print(f"total issues: {len(issues)}", file=sys.stderr)

# load plugins
with open(os.path.join(ROOT, "src", "data", "plugins.json"), encoding="utf-8") as f:
    db = json.load(f)


def norm(u):
    u = (u or "").strip().lower()
    u = re.sub(r"^https?://", "", u)
    if u.endswith(".git"):
        u = u[:-4]
    return u.rstrip("/")


# url -> plugin (first wins)
url_map = {}
for cat, items in db.items():
    for p in items:
        if p.get("url"):
            url_map.setdefault(norm(p["url"]), p)

# repo renames: old issue URL -> current catalog URL
ALIASES = {
    "github.com/wwumit/dsh-skill-hub": "github.com/wwumit/dsh-compliancehub",
}

RE = re.compile(r"github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?(?:[#/)\s]|$)", re.I)

contrib = {}   # author -> {plugin_name: plugin}
avatars = {}   # author -> avatar_url
unmatched = []  # (author, url) for URLs we couldn't map, for review
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
    plugins = []
    for name in sorted(pmap):
        p = pmap[name]
        plugins.append({
            "name": p.get("name"),
            "slug": p.get("slug") or p.get("name"),
            "npm": bool(p.get("npm")),
            "pkg": p.get("pkg") or "",
        })
    result.append({"github": author, "avatar": avatars.get(author, ""), "plugins": plugins})

result.sort(key=lambda c: (-len(c["plugins"]), c["github"].lower()))

with open(os.path.join(ROOT, "src", "data", "contributors.json"), "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)

print(json.dumps(result, ensure_ascii=False, indent=1))
print(f"\n# unmatched URLs ({len(unmatched)}):", file=sys.stderr)
for a, u in sorted(set(unmatched)):
    print(f"  {a}  {u}", file=sys.stderr)
