#!/usr/bin/env bash
set -uo pipefail
cd /root/dshbase || exit 1
git checkout -- src/data/plugins.json

# restore flat credentials format (verify-runtime.sh compatible)
KEY=$(python3 - <<'PY'
import re
for path in ("/root/.dsh/.credentials.yaml",):
    try:
        txt = open(path, encoding="utf-8").read()
    except FileNotFoundError:
        continue
    for pat in (r"DEEPSEEK_API_KEY:\s*(\S+)", r"refs:\s*\n\s*DEEPSEEK_API_KEY:\s*(\S+)"):
        m = re.search(pat, txt)
        if m:
            print(m.group(1))
            raise SystemExit
raise SystemExit("no key")
PY
)

cat > /root/.dsh/.credentials.yaml <<EOF
DEEPSEEK_API_KEY: $KEY
TOKEN_PLAN_API_KEY: $KEY
EOF
chmod 600 /root/.dsh/.credentials.yaml
export DEEPSEEK_API_KEY="$KEY"

cat > /tmp/issue-verify.tsv <<'EOF'
dsh-siyuan	dsh-siyuan
dsh-essentials-bundle	github:lussey820/dsh-essentials-bundle
dsh-full-access-switch	github:xtd1145/dsh-full-access-switch
dsh-client-ui-prism	github:mantonlove/dsh-prism-plugin
dsh-opencode-whale-widget	github:functy23/Opencode-Whale-Widget
dsh-qingagent	dsh-qingagent
EOF

export VERIFY_LIST=/tmp/issue-verify.tsv
export VERIFY_OUT=/tmp/issue-verify-l3.tsv
export WORKERS=3
bash scripts/verify-runtime.sh > /tmp/issue-verify-l3.log 2>&1
echo "=== L3 ==="
cat /tmp/issue-verify-l3.tsv

# restore detailed notes before merge clobbers - we'll merge manually after
cp src/data/plugins.json /tmp/plugins-before-merge.json
python3 scripts/merge-verify.py /tmp/issue-verify-l3.tsv

python3 - /tmp/issue-verify-l3.tsv src/data/plugins.json /tmp/issue-verify-l4.tsv <<'PY'
import json, re, sys
results, data_path, out_path = sys.argv[1:4]
need = set()
for line in open(results, encoding="utf-8"):
    line = line.strip()
    if not line or "\t" not in line:
        continue
    name, st = line.split("\t", 1)
    if st.strip() == "web-only":
        need.add(name)
db = json.load(open(data_path, encoding="utf-8"))
rows = []
for items in db.values():
    for p in items:
        if p.get("name") not in need:
            continue
        stars = int(p.get("stars") or 0)
        name = p["name"]
        if p.get("npm") and p.get("pkg"):
            src, kind = p["pkg"], "npm"
        else:
            m = re.search(r"github\.com/([^/]+/[^/]+)", p.get("url") or "", re.I)
            if not m:
                continue
            src, kind = "github:" + m.group(1).rstrip("/"), "git"
        rows.append((stars, name, src, kind))
rows.sort(reverse=True)
with open(out_path, "w", encoding="utf-8") as f:
    for stars, name, src, kind in rows:
        f.write(f"{stars}\t{name}\t{src}\t{kind}\n")
print(f"L4 candidates: {len(rows)}")
PY

if [ -s /tmp/issue-verify-l4.tsv ]; then
  bash scripts/verify-webonly.sh /tmp/issue-verify-l4.tsv > /tmp/issue-verify-l4.log 2>&1
  echo "=== L4 ==="
  cat /tmp/issue-verify-l4-results.tsv
  python3 scripts/merge-webonly.py /tmp/issue-verify-l4-results.tsv
fi

echo "=== FINAL ==="
python3 - <<'PY'
import json
names = [
  "dsh-siyuan", "dsh-essentials-bundle", "dsh-full-access-switch",
  "dsh-client-ui-prism", "dsh-opencode-whale-widget", "dsh-qingagent",
]
db = json.load(open("src/data/plugins.json", encoding="utf-8"))
for items in db.values():
    for p in items:
        if p["name"] in names:
            print(f"{p['name']}\t{p.get('test')}\t{p.get('webonly','')}\t{(p.get('note') or '')[:100]}")
PY
