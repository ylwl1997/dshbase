#!/usr/bin/env bash
# 全量插件验证（L1 安装 + L2 加载）：对每个插件 fresh-profile 安装 + dump-config，
# 只升级为 verified，绝不在单次（可能 flaky）运行降级已有状态。
#
# 依赖：node + pnpm + dsh（已在 PATH）。
# 用法：bash scripts/verify-all.sh [起始索引] [结束索引]   # 支持分批（配合 CI matrix）
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DSH_BASE_SPEC="$("$PYTHON" "$SCRIPT_DIR/dsh_official_spec.py" @deepseek-ai/dsh-base)" || exit 1
DATA="src/data/plugins.json"
export DSH_HOME="${DSH_HOME:-/tmp/dsh-verify}"
mkdir -p "$DSH_HOME/profiles"

# 1. 列出待验证插件：name<TAB>source（npm 包名 或 github:owner/repo）
"$PYTHON" - "$DATA" <<'PYEOF' > /tmp/verify-list.tsv
import json, re, sys, os
d = json.load(open(sys.argv[1], encoding='utf-8'))
filt = os.environ.get('VERIFY_FILTER', '')
def keep(p):
    if filt == 'pending-github':
        return p.get('test') in ('pending', 'listed') and not p.get('npm')
    if filt == 'pending':
        return p.get('test') in ('pending', 'listed')
    return True
out = []
for items in d.values():
    for p in items:
        if not keep(p):
            continue
        name = p['name']
        src = ''
        if p.get('npm') and p.get('pkg'):
            src = p['pkg']
        elif p.get('url'):
            m = re.search(r'github\.com/([^/]+/[^/]+)', p['url'])
            if m:
                src = 'github:' + m.group(1).rstrip('/')
        if src:
            out.append((name, src))
for name, src in out:
    print(name + '\t' + src)
PYEOF

# 支持分批：取 [start, end) 切片
start="${1:-0}"
end="${2:-999999}"
sed -n "$((start + 1)),$((end))p" /tmp/verify-list.tsv > /tmp/verify-batch.tsv
total=$(wc -l < /tmp/verify-batch.tsv)
echo "待验证: $total 个（切片 $start..$end）"

: > /tmp/verify-results.tsv
i=0
while IFS=$'\t' read -r name src; do
  [ -z "$name" ] && continue
  i=$((i + 1))
  prof="v_$(echo "$name" | tr -cd 'a-zA-Z0-9_-')"
  profdir="$DSH_HOME/profiles/$prof"
  rm -rf "$profdir"; mkdir -p "$profdir"

  # 预写 pnpm-workspace.yaml：允许原生依赖 build（pnpm v11 默认阻止）
  cat > "$profdir/pnpm-workspace.yaml" <<'YAML'
allowBuilds:
  '@deepseek-ai/dsh-subprocess-local': true
  '@google/genai': true
  koffi: true
  node-pty: true
  protobufjs: true
YAML

  status="unknown"
  log="/tmp/verify-$name.log"

  # DSH_BASE_SPEC is the version the installed @deepseek-ai/dsh@latest CLI depends on.
  installed=0
  for attempt in 1 2 3; do
    if timeout 240 dsh plugin --profile "$prof" add "$DSH_BASE_SPEC" "$src" >"$log" 2>&1; then
      installed=1
      break
    fi
    # git 托管 prepare：把 pnpm 打印的精确 onlyBuiltDependencies / allowBuilds key
    # 写入本 profile 再重试。范围只限本仓库 verify 安装，不放宽 engines，
    # 也不使用 dsh plugin allow-version --accept-risk。占位符仍改成 true。
    new_keys=$(python3 - "$log" "$SCRIPT_DIR/verify-pilot.py" <<'PYEOF'
import runpy, sys
log = open(sys.argv[1], encoding='utf-8', errors='replace').read()
mod = runpy.run_path(sys.argv[2])
print('\n'.join(mod['parse_allow_build_keys'](log)))
PYEOF
)
    if [ -n "$new_keys" ]; then
      python3 - "$profdir/pnpm-workspace.yaml" "$new_keys" <<'PYEOF'
import sys
ws, keys = sys.argv[1], sys.argv[2].splitlines()
s = open(ws, encoding='utf-8').read()
add = []
for k in keys:
    kk = k.strip()
    if not kk:
        continue
    quoted = f'"{kk}": true'
    if f'  {quoted}' not in s and f'  {kk}:' not in s:
        add.append(f'  {quoted}')
if add:
    lines = s.splitlines()
    out = []
    inserted = False
    for line in lines:
        out.append(line)
        if line.strip() == 'allowBuilds:' and not inserted:
            out.extend(add)
            inserted = True
    if not inserted:
        out = ['allowBuilds:'] + add + out
    open(ws, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print('added allowBuilds:', ', '.join(k.strip() for k in keys if k.strip()), file=sys.stderr)
PYEOF
    fi
    sed -i 's/set this to true or false/true/g' "$profdir/pnpm-workspace.yaml" 2>/dev/null
    sleep 8
  done

  if [ "$installed" -eq 1 ]; then
    if timeout 90 dsh --profile "$prof" --dump-config >/dev/null 2>>"$log"; then
      status="ok"
    else
      status="load-fail"
    fi
  elif grep -qiE "failed to connect|could not connect|ENOTFOUND|ETIMEDOUT|UND_ERR|ECONNRESET|ECONNREFUSED|network is unreachable|git ls-remote.*fatal" "$log"; then
    status="network-fail"
  else
    status="install-fail"
  fi

  printf '%s\t%s\n' "$name" "$status" >> /tmp/verify-results.tsv
  echo "[$i/$total] $name -> $status"
done < /tmp/verify-batch.tsv

echo "=== 结果文件 /tmp/verify-results.tsv（$total 条）==="

