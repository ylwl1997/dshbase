#!/usr/bin/env bash
# Daily compatibility check: for every npm-published plugin, do a fresh-profile
# install + --dump-config, and write the result back into plugins.json so the
# directory/dashboard stay current. Runs in GitHub Actions (ubuntu-latest).
#
# Requires on PATH: node, pnpm, dsh (installed by the workflow).
# Writes `test` (verified) + `testDate` on npm plugins whose install+boot pass,
# plus an informational `bareNpm` (bare `npm install` + import smoke).
#
# Platform guard: win32/macos-only plugins are NOT auto-upgraded to "verified"
# by this Linux CI — it can confirm "installs" but not the platform-specific
# behavior, so they keep their curated/pending status.
#
# Web-frontend registration (the "loaded without registering" gap that
# --dump-config cannot see) is covered separately by
# scripts/check-web-registration.sh on the Linux server.
set -uo pipefail

DATA="src/data/plugins.json"
export DSH_HOME="${DSH_HOME:-$(mktemp -d)}"
RESULTS="$(mktemp)"
BARENPM="$(mktemp)"

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

  # B. bare `npm install <pkg>` + import smoke. `dsh plugin add` resolves the
  # plugin's externals via the harness's own dependency set, so an external the
  # author put in devDependencies (instead of dependencies) only breaks on a
  # bare install. Informational only — never changes `test`.
  bare="unknown"
  btmp="$(mktemp -d)"
  if ( cd "$btmp" && timeout 120 npm install --no-audit --no-fund "$pkg" >/dev/null 2>&1 ); then
    if timeout 30 node --input-type=module -e "import('$pkg').catch(()=>process.exit(1))" >/dev/null 2>"$btmp/imp.err"; then
      bare="ok"
    elif grep -qE "ERR_MODULE_NOT_FOUND|Cannot find (module|package)" "$btmp/imp.err"; then
      bare="missing-dep"
    else
      bare="other"
    fi
  else
    bare="install-fail"
  fi
  rm -rf "$btmp"

  printf '%s\t%s\n' "$name" "$status" >> "$RESULTS"
  printf '%s\t%s\n' "$name" "$bare" >> "$BARENPM"
  echo "[$i/$total] $name -> $status (bare=$bare)"
done < /tmp/dsh-npm-plugins.tsv

# 3. write results back into plugins.json
python3 - "$DATA" "$RESULTS" "$BARENPM" <<'PYEOF'
import json, sys
from datetime import date, timezone

data_path, results_path, bare_path = sys.argv[1], sys.argv[2], sys.argv[3]
res = {}
for line in open(results_path, encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    name, status = line.split("\t", 1)
    res[name] = status
bare = {}
for line in open(bare_path, encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    name, b = line.split("\t", 1)
    bare[name] = b

today = date.today().isoformat()
d = json.load(open(data_path, encoding="utf-8"))
changed = 0
for items in d.values():
    for p in items:
        if not (p.get("npm") and p.get("name") in res):
            continue
        if p["name"] in bare:
            p["bareNpm"] = bare[p["name"]]
        st = res[p["name"]]
        old = p.get("test")
        pf = p.get("platform") or "any"
        # 平台守卫：win32/macos-only 在 Linux 上只确认「装得上」，不升级 verified
        if pf in ("win32", "macos"):
            continue
        # 保守策略：CI 只做正向确认（升级为 verified），绝不降级已收录状态。
        if st == "ok" and old != "verified":
            p["test"] = "verified"
            p["testDate"] = today
            changed += 1
json.dump(d, open(data_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"upgraded {changed} plugins to verified in {data_path}")
PYEOF
