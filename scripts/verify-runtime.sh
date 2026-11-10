#!/usr/bin/env bash
# 全量插件验证（L1 安装 + L2 加载 + L3 headless 问答），并行执行。
# 判定：ok=全过 / web-only=GUI插件(headless无服务,非失败) / load-fail=加载失败 / runtime-fail=问答失败 / install-fail=装不上 / network-fail=网络问题
# 用法：
#   bash scripts/verify-runtime.sh                    # 全部 pending
#   VERIFY_FILTER=pending-npm bash scripts/verify-runtime.sh   # 仅 npm 源 pending
#   WORKERS=6 bash scripts/verify-runtime.sh          # 并行度（默认 6）
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PYTHON="${PYTHON:-python3}"
# Versions the installed @deepseek-ai/dsh@latest CLI depends on. Not each
# package's own latest dist-tag, and not a version frozen in this repo.
DSH_BASE_SPEC="$("$PYTHON" "$SCRIPT_DIR/dsh_official_spec.py" @deepseek-ai/dsh-base)" || exit 1
DSH_HEADLESS_SPEC="$("$PYTHON" "$SCRIPT_DIR/dsh_official_spec.py" @deepseek-ai/dsh-headless)" || exit 1
export DSH_BASE_SPEC DSH_HEADLESS_SPEC
DATA="src/data/plugins.json"
# dsh 实际把 profile 放在 ~/.dsh/profiles（不认 DSH_HOME 环境变量）
export PROFILE_ROOT="${DSH_PROFILE_ROOT:-$HOME/.dsh/profiles}"
mkdir -p "$PROFILE_ROOT"
WORKERS="${WORKERS:-6}"

# credentials：从环境变量 DEEPSEEK_API_KEY 写入 ~/.dsh/.credentials.yaml（key 不进脚本）
if [ -n "${DEEPSEEK_API_KEY:-}" ]; then
  mkdir -p "$HOME/.dsh"
  cat > "$HOME/.dsh/.credentials.yaml" <<YEOF
DEEPSEEK_API_KEY: $DEEPSEEK_API_KEY
YEOF
  chmod 600 "$HOME/.dsh/.credentials.yaml"
fi

# 1. 生成待验证列表：name<TAB>source（或使用外部列表 VERIFY_LIST）。
#    列表用 PID 隔离，避免多实例并行时互相覆盖 /tmp/verify-list.tsv。
if [ -n "${VERIFY_LIST:-}" ] && [ -f "$VERIFY_LIST" ]; then
  LIST_FILE="/tmp/verify-list-$$.tsv"
  tr -d '\r' < "$VERIFY_LIST" > "$LIST_FILE"   # 去 CR（Windows 行尾）
else
  LIST_FILE="/tmp/verify-list-$$.tsv"
"$PYTHON" - "$DATA" <<'PYEOF' > "$LIST_FILE"
import json, re, sys, os
d = json.load(open(sys.argv[1], encoding='utf-8'))
filt = os.environ.get('VERIFY_FILTER', '')
def keep(p):
    if p.get('test') not in ('pending', 'listed'):
        return False
    if filt == 'pending-github':
        return not p.get('npm')
    if filt == 'pending-npm':
        return bool(p.get('npm'))
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
fi

total=$(wc -l < "$LIST_FILE")
echo "待验证: $total 个（并行 $WORKERS 路）" >&2

# 2. 单插件验证函数
verify_one() {
  local name="$1" src="$2"
  local prof="v_$(echo "$name" | tr -cd 'a-zA-Z0-9_-')"
  local profdir="$PROFILE_ROOT/$prof"
  # 无论成功/失败/超时退出，都清理该验证 profile，防止 ~/.dsh/profiles 被 node_modules 堆满
  trap 'rm -rf "$profdir" 2>/dev/null' RETURN
  rm -rf "$profdir"; mkdir -p "$profdir"
  local log="/tmp/verify-$prof.log"   # sanitize (scoped pkg @a/b has /)
  local status="unknown"
  local installed=0
  # allowBuilds 白名单：native 依赖先放行。git 托管插件的 prepare 被
  # ERR_PNPM_GIT_DEP_PREPARE_NOT_ALLOWED / onlyBuiltDependencies 拦住时，
  # 把 pnpm 打印的精确 key 写入本 profile 的 allowBuilds 再重试
  # （解析在 scripts/verify-pilot.py）。范围只限本仓库 verify 安装，
  # 不放宽 engines，也不使用 dsh plugin allow-version --accept-risk。
  # dangerouslyAllowAllBuilds 在 pnpm 11.22 已失效。
  {
    echo "allowBuilds:"
    echo "  '@deepseek-ai/dsh-subprocess-local': true"
    echo "  '@google/genai': true"
    echo "  koffi: true"
    echo "  node-pty: true"
    echo "  protobufjs: true"
  } > "$profdir/pnpm-workspace.yaml"
  for attempt in 1 2 3; do
    # Specs come from the installed CLI (see DSH_BASE_SPEC). Transitive
    # @deepseek-ai/* versions stay on what those packages declare.
    if timeout 240 dsh plugin --profile "$prof" add "$DSH_BASE_SPEC" "$DSH_HEADLESS_SPEC" "$src" >"$log" 2>&1; then
      installed=1; break
    fi
    # 解析 pnpm 提示的 allowBuilds key（含 @/:/ 的 key 必须加引号，否则 YAML 解析错）
    local new_keys
    new_keys=$(python3 - "$log" "$SCRIPT_DIR/verify-pilot.py" <<'PYEOF'
import runpy, sys
log = open(sys.argv[1], encoding='utf-8', errors='replace').read()
mod = runpy.run_path(sys.argv[2])
print('\n'.join(mod['parse_allow_build_keys'](log)))
PYEOF
)
    if [ -z "$new_keys" ]; then
      sleep 5; continue
    fi
    python3 - "$prof" "$new_keys" <<'PYEOF'
import sys, os
prof, keys = sys.argv[1], sys.argv[2].splitlines()
ws = os.path.expanduser(f'~/.dsh/profiles/{prof}/pnpm-workspace.yaml')
if not os.path.exists(ws):
    sys.exit(0)
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
    open(ws, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print('added allowBuilds:', ', '.join(kk for kk in keys), file=sys.stderr)
PYEOF
    sleep 5
  done

  if [ "$installed" -eq 1 ]; then
    if timeout 90 dsh --profile "$prof" --dump-config >/dev/null 2>>"$log"; then
      local out rc
      out=$(timeout 90 dsh --profile "$prof" "Reply with exactly: OK" 2>>"$log")
      rc=$?
      if [ "$rc" -eq 0 ] && printf '%s' "$out" | grep -q "OK"; then
        status="ok"
      elif grep -q "waiting for service" "$log"; then
        # entry 依赖 GUI 服务（webServer/storage/workspace/connection 等），headless 下服务不满足，
        # 这是 web UI / 全运行时插件，不是失败。
        status="web-only"
      else
        status="runtime-fail"
      fi
    else
      status="load-fail"
    fi
  elif grep -qiE "failed to connect|could not connect|ENOTFOUND|ETIMEDOUT|UND_ERR|ECONNRESET|ECONNREFUSED|network is unreachable|git ls-remote.*fatal|EAI_AGAIN" "$log"; then
    status="network-fail"
  else
    status="install-fail"
  fi

  printf '%s\t%s\n' "$name" "$status"
  echo "[$name] $status" >&2
  # 清理验证期 profile，避免 ~/.dsh/profiles 被 node_modules 堆满 (见 verify-runtime.sh)
  rm -rf "$profdir" 2>/dev/null
}
export -f verify_one

# 3. 并行执行
cat "$LIST_FILE" | xargs -P "$WORKERS" -n 2 bash -c 'verify_one "$0" "$1"' > "${VERIFY_OUT:-/tmp/verify-results.tsv}"

echo "=== 结果文件 ${VERIFY_OUT:-/tmp/verify-results.tsv} ===" >&2
