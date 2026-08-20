#!/usr/bin/env bash
# Full verify pipeline: L1+L2+L3 (headless) then L4 (web CDP) for web-only.
#
# Rule:
#   L3 status=ok        → verified (no L4 needed)
#   L3 status=web-only  → MUST run L4 (verify-webonly.sh / CDP); only L4 ok → verified
#   other L3 failures   → stay pending
#
# Usage:
#   bash scripts/verify-full.sh                         # all pending via verify-runtime
#   VERIFY_LIST=list.tsv bash scripts/verify-full.sh    # custom name<TAB>src list
#   WORKERS=6 bash scripts/verify-full.sh
#
# Outputs:
#   ${VERIFY_OUT:-/tmp/verify-results.tsv}           L3 headless
#   ${WEBONLY_OUT:-/tmp/webonly-l4-results.tsv}      L4 web CDP (subset)
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

VERIFY_OUT="${VERIFY_OUT:-/tmp/verify-results.tsv}"
WEBONLY_LIST="${WEBONLY_LIST:-/tmp/webonly-l4-list.tsv}"
WEBONLY_OUT="${WEBONLY_OUT:-/tmp/webonly-l4-results.tsv}"
DATA="${DATA:-src/data/plugins.json}"

echo "=== L1–L3 headless (verify-runtime.sh) ===" >&2
WORKERS="${WORKERS:-6}" VERIFY_OUT="$VERIFY_OUT" bash "$SCRIPT_DIR/verify-runtime.sh"
echo "L3 results: $VERIFY_OUT" >&2
cut -f2 "$VERIFY_OUT" 2>/dev/null | sort | uniq -c >&2 || true

# Build L4 list from L3 web-only rows
python3 - "$VERIFY_OUT" "$DATA" "$WEBONLY_LIST" <<'PY'
import json, re, sys
results, data_path, out_path = sys.argv[1:4]
need = set()
for line in open(results, encoding="utf-8", errors="replace"):
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
print(f"L4 candidates: {len(rows)}", file=sys.stderr)
for stars, name, src, kind in rows:
    print(f"  {stars:5d} {name} {src}", file=sys.stderr)
PY

n_l4=$(wc -l < "$WEBONLY_LIST" | tr -d ' ')
if [ "${n_l4:-0}" -eq 0 ]; then
  echo "=== No web-only plugins — L4 skipped; headless ok is enough ===" >&2
  : > "$WEBONLY_OUT"
  exit 0
fi

echo "=== L4 web CDP (verify-webonly.sh) for $n_l4 web-only plugin(s) ===" >&2
# verify-webonly writes <list>-results.tsv next to the list file
bash "$SCRIPT_DIR/verify-webonly.sh" "$WEBONLY_LIST"
# normalize output path
src_results="${WEBONLY_LIST%.tsv}-results.tsv"
if [ -f "$src_results" ]; then
  cp "$src_results" "$WEBONLY_OUT"
fi
echo "L4 results: $WEBONLY_OUT" >&2
cut -f2 "$WEBONLY_OUT" 2>/dev/null | sort | uniq -c >&2 || true
echo "=== Done. Merge with: python3 scripts/merge-verify.py $VERIFY_OUT && python3 scripts/merge-webonly.py $WEBONLY_OUT ===" >&2
