#!/usr/bin/env bash
set -uo pipefail
cd /root/dshbase || exit 1

KEY=$(python3 - <<'PY'
import re
txt = open("/root/.dsh/.credentials.yaml", encoding="utf-8").read()
m = re.search(r"DEEPSEEK_API_KEY:\s*(\S+)", txt)
print(m.group(1) if m else "")
PY
)
[ -z "$KEY" ] && { echo "no DEEPSEEK_API_KEY"; exit 1; }

cat > /root/.dsh/.credentials.yaml <<EOF
version: 1
refs:
  DEEPSEEK_API_KEY: $KEY
  TOKEN_PLAN_API_KEY: $KEY
EOF
chmod 600 /root/.dsh/.credentials.yaml
export DEEPSEEK_API_KEY="$KEY"

printf '%s\n' \
  '0	dsh-siyuan	dsh-siyuan	npm' \
  '0	dsh-client-ui-prism	github:mantonlove/dsh-prism-plugin	git' \
  '0	dsh-opencode-whale-widget	github:functy23/Opencode-Whale-Widget	git' \
  '0	dsh-essentials-bundle	github:lussey820/dsh-essentials-bundle	git' \
  '0	dsh-qingagent	dsh-qingagent	npm' \
  > /tmp/verify-batch2.tsv

export VERIFY_LIST=/tmp/verify-batch2.tsv
export VERIFY_OUT=/tmp/verify-batch2-results.tsv
export WORKERS=3
bash scripts/verify-runtime.sh > /tmp/verify-batch2.log 2>&1
echo "=== L3 RESULTS ==="
cat /tmp/verify-batch2-results.tsv

printf '%s\n' \
  '0	dsh-essentials-bundle	github:lussey820/dsh-essentials-bundle	git' \
  '0	dsh-client-ui-prism	github:mantonlove/dsh-prism-plugin	git' \
  '0	dsh-opencode-whale-widget	github:functy23/Opencode-Whale-Widget	git' \
  > /tmp/webonly-batch2.tsv

bash scripts/verify-webonly.sh /tmp/webonly-batch2.tsv > /tmp/webonly-batch2.log 2>&1
echo "=== L4 RESULTS ==="
cat /tmp/webonly-batch2-results.tsv
echo "=== L4 SUMMARY ==="
tail -20 /tmp/webonly-batch2.log
