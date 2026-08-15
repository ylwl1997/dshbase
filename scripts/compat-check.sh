#!/usr/bin/env bash
# Daily compatibility check: for every npm-published plugin, do a fresh-profile
# install + --dump-config, and write the result back into plugins.json so the
# directory/dashboard stay current. Runs in GitHub Actions (ubuntu-latest).
#
# Requires on PATH: node, pnpm, dsh (installed by the workflow).
# Writes `test` (ok / load-fail / install-fail) and `testDate` on npm plugins only;
# git-source plugins keep their curated status.
set -uo pipefail

DATA="src/data/plugins.json"
export DSH_HOME="${DSH_HOME:-$(mktemp -d)}"
RESULTS="$(mktemp)"

# 1. list npm plugins: name<TAB>package
python3 - "$DATA" <<'PYEOF' > /tmp/dsh-npm-plugins.tsv
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
for items in d.values():
    for p in items:
        if p.get("npm") and p.get("pkg"):
            print(p["name"] + "\t" + p["pkg"])
PYEOF

total=$(wc -l < /tmp/dsh-npm-plugins.tsv)
echo "testing $total npm plugins (DSH_HOME=$DSH_HOME)"

# 2. test each in an isolated profile
i=0
while IFS=$'\t' read -r name pkg; do
  [ -z "$name" ] && continue
  i=$((i+1))
  log="/tmp/compat-$name.log"
  status="unknown"

  # fresh profile: `dsh plugin add` inits the profile, installs, and reconciles
  # bundle plugins into dsh.profile.bundles automatically.
  if timeout 240 dsh plugin --profile "$name" add "@deepseek-ai/dsh-base" "$pkg" >"$log" 2>&1; then
    if timeout 90 dsh --profile "$name" --dump-config >/dev/null 2>>"$log"; then
      status="ok"
    else
      status="load-fail"
    fi
  else
    status="install-fail"
  fi

  printf '%s\t%s\n' "$name" "$status" >> "$RESULTS"
  echo "[$i/$total] $name -> $status"
done < /tmp/dsh-npm-plugins.tsv

# 3. write results back into plugins.json
python3 - "$DATA" "$RESULTS" <<'PYEOF'
import json, sys
from datetime import date, timezone

data_path, results_path = sys.argv[1], sys.argv[2]
res = {}
for line in open(results_path, encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    name, status = line.split("\t", 1)
    res[name] = status

today = date.today().isoformat()
d = json.load(open(data_path, encoding="utf-8"))
changed = 0
for items in d.values():
    for p in items:
        if p.get("npm") and p.get("name") in res:
            st = res[p["name"]]
            old = p.get("test")
            # 保守策略：CI 只做正向确认（升级为 ok），绝不在单次（可能网络不稳）运行时
            # 降级已收录的状态 —— install-fail/load-fail 需要多次连续失败再人工判断。
            if st == "ok" and old != "ok":
                p["test"] = "ok"
                p["testDate"] = today
                changed += 1
json.dump(d, open(data_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"upgraded {changed} plugins to ok in {data_path}")
PYEOF
