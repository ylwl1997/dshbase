#!/usr/bin/env bash
# Web-frontend registration check (L4-lite).
#
# --dump-config only proves a bundle landed in the config tree; it cannot see
# whether the *client* bundle actually registered in the web UI. A bundle that
# "loads without registering" makes the web UI report "Failed to load plugins"
# and can drag down every other plugin's UI. This boot-and-grep is a best-effort
# detector for that gap. Run it on the Linux server where `dsh web` works
# (see [[dsh-plugin-verification]]), not in the light daily CI.
#
# Usage:
#   DEEPSEEK_API_KEY=... bash scripts/check-web-registration.sh
#   WEB_PLUGINS="dsh-win32 dsh-what-changed" bash scripts/check-web-registration.sh
#
# Env:
#   WEB_PLUGINS   space-separated pkg names to test (default: every npm pkg)
#   WEB_PORT      port for the web server (default 3199)
#   WEB_TIMEOUT   seconds to let it boot before grepping (default 60)
#
# IMPORTANT: experimental. The real "loaded without registering" signal may only
# surface in the browser JS console, in which case use the CDP flow (~/webverify/
# on the server) for a definitive per-plugin L3. This script only flags plugins
# whose name appears on a log line containing a known registration-failure marker.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SCRIPT_DIR
DATA="$SCRIPT_DIR/../src/data/plugins.json"
PROFILE_ROOT="${DSH_PROFILE_ROOT:-$HOME/.dsh/profiles}"
PORT="${WEB_PORT:-3199}"
TIMEOUT="${WEB_TIMEOUT:-60}"
PYTHON="${PYTHON:-python3}"

# 0. credentials
if [ -n "${DEEPSEEK_API_KEY:-}" ]; then
  mkdir -p "$HOME/.dsh"
  cat > "$HOME/.dsh/.credentials.yaml" <<YEOF
DEEPSEEK_API_KEY: $DEEPSEEK_API_KEY
YEOF
  chmod 600 "$HOME/.dsh/.credentials.yaml"
fi

# 1. list of npm packages under test
"$PYTHON" - "$DATA" <<'PYEOF' > /tmp/webcheck-pkgs.txt
import json, sys, os
d = json.load(open(sys.argv[1], encoding='utf-8'))
sel = os.environ.get('WEB_PLUGINS', '').split()
pkgs = []
for items in d.values():
    for p in items:
        if not (p.get('npm') and p.get('pkg')):
            continue
        if sel and p['name'] not in sel and p['pkg'] not in sel:
            continue
        pkgs.append(p['pkg'])
for x in pkgs:
    print(x)
PYEOF

total=$(wc -l < /tmp/webcheck-pkgs.txt)
echo "web-registration check: $total npm packages" >&2

# 2. one shared web profile
prof="webcheck"
profdir="$PROFILE_ROOT/$prof"
rm -rf "$profdir"; mkdir -p "$profdir"
{
  echo "dangerouslyAllowAllBuilds: true"
  echo "overrides:"
  cat "$SCRIPT_DIR/dsh-overrides.yaml"
} > "$profdir/pnpm-workspace.yaml"

# base surface first (web-app, NOT headless — the two are parallel surfaces)
dsh plugin --profile "$prof" add "@deepseek-ai/dsh-base@0.1.0-rc.8" "@deepseek-ai/dsh-web-app@0.1.0-rc.8" >/tmp/webcheck-base.log 2>&1 || true
while read -r pkg; do
  [ -z "$pkg" ] && continue
  dsh plugin --profile "$prof" add "$pkg" >/dev/null 2>>/tmp/webcheck-base.log || true
done < /tmp/webcheck-pkgs.txt

# 3. boot web, capture log, grep
LOG=/tmp/webcheck-web.log
timeout "$TIMEOUT" dsh --profile "$prof" web --host 127.0.0.1 --port "$PORT" --trusted-host >"$LOG" 2>&1 &
WPID=$!
sleep "$TIMEOUT"
kill "$WPID" 2>/dev/null || true

echo "=== registration-failure markers ===" >&2
grep -iE "failed to load plugin|loaded without registering|overlay-missing|failed to register|registration failed|__ModuleLoader__" "$LOG" || echo "(none found)" >&2

echo "=== per-plugin suspicion (name on an error line) ===" >&2
"$PYTHON" - "$LOG" /tmp/webcheck-pkgs.txt <<'PYEOF'
import sys, re
log = open(sys.argv[1], encoding='utf-8', errors='replace').read()
lines = [l for l in log.splitlines() if re.search(r'failed to load plugin|loaded without registering|overlay-missing|failed to register|registration failed', l, re.I)]
pkgs = [l.strip() for l in open(sys.argv[2], encoding='utf-8') if l.strip()]
flagged = [p for p in pkgs if any(p in l or p.split('/')[-1] in l for l in lines)]
if flagged:
    for p in flagged:
        print('  ' + p)
else:
    print('  (none)')
PYEOF

echo "full log: $LOG" >&2
