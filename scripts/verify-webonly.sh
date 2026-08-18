#!/usr/bin/env bash
# web-only 插件批量验证（独立临时 profile 方案）
#
# 每个插件建独立 profile v_<name>（dsh-base + dsh-web-app + 插件），
# boot 后跑 l3.mjs CDP 端到端，判定并记录结果，测完删除 profile。
# 不碰干净的 web 基线 profile；插件间互不污染。
#
# 用法:
#   bash scripts/verify-webonly.sh <list.tsv>            # 批量
#   bash scripts/verify-webonly.sh --one dsh-xxx         # 单个（用 pkg 或 github:owner/repo）
#   bash scripts/verify-webonly.sh --continue            # 跳过 results.tsv 里已记录的
#
# 输入 list.tsv: 每行  stars<TAB>name<TAB>src<TAB>npm|git
#   其中 src = npm 包名 或 github:owner/repo
# 输出: <list 同目录>/webonly-results.tsv  每行 name<TAB>status
#   status: ok / load-fail / install-fail / runtime-fail
#
# 依赖（服务器已装）:
#   dsh 0.1.0-rc.6, node, pnpm 11, puppeteer+Chromium (~/webverify/l3.mjs)
#   $DSH_OVERRIDES  可指定 overrides yaml 路径（默认仓库 scripts/dsh-overrides.yaml）
set -uo pipefail

PROF_ROOT="$HOME/.dsh/profiles"
WEB_PORT="${WEB_PORT:-3080}"
CHROME='/root/.cache/puppeteer/chrome/linux-152.0.7977.42/chrome-linux64/chrome'
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SCRIPT_DIR
WEBVERIFY_DIR="${WEBVERIFY_DIR:-$HOME/webverify}"
L3="$WEBVERIFY_DIR/l3.mjs"
export L3

# overrides：默认取仓库里 189 包全 pin 版本
if [ -z "${DSH_OVERRIDES:-}" ]; then
  DSH_OVERRIDES="$SCRIPT_DIR/dsh-overrides.yaml"
fi

log() { echo "[$(date '+%H:%M:%S')] $*" >&2; }

make_workspace() {
  local prof="$1"
  {
    echo "allowBuilds:"
    echo "  '@deepseek-ai/dsh-subprocess-local': true"
    echo "  '@google/genai': true"
    echo "  koffi: true"
    echo "  node-pty: true"
    echo "  protobufjs: true"
    echo "overrides:"
    cat "$DSH_OVERRIDES"
  } > "$PROF_ROOT/$prof/pnpm-workspace.yaml"
}

# 启动/停止 web 服务（用指定 profile 和端口）
web_stop() {
  pkill -f 'dsh --profile v_' 2>/dev/null
  pkill -f 'dsh web' 2>/dev/null
  sleep 2
}

web_boot() {
  local prof="$1" port="$2"
  cd /root || return 1
  setsid nohup script -qfc "dsh --profile $prof --host 127.0.0.1 --port $port" \
    /dev/null > /tmp/webverify-$prof.log 2>&1 < /dev/null &
  disown
  # 等端口起来（最多 90s）
  for _ in $(seq 1 45); do
    if curl -s -o /dev/null --max-time 3 "http://127.0.0.1:$port/"; then
      return 0
    fi
    sleep 2
  done
  return 1
}

verify_one() {
  local name="$1" src="$2"
  local prof="v_$(echo "$name" | tr -cd 'a-zA-Z0-9_-')"
  local logf="/tmp/verify-$name.log"
  local status=""

  log "== $name  ($src)  profile=$prof =="

  # 1. 建独立 profile + workspace（allowBuilds + overrides）
  mkdir -p "$PROF_ROOT/$prof"
  make_workspace "$prof"

  # 2. L1+L2: 装 base+web-app+插件，dump-config 判定
  if timeout 300 dsh plugin --profile "$prof" add \
      "@deepseek-ai/dsh-base@0.1.0-rc.6" \
      "@deepseek-ai/dsh-web-app@0.1.0-rc.6" \
      "$src" > "$logf" 2>&1; then
    if timeout 90 dsh --profile "$prof" --dump-config >/dev/null 2>>"$logf"; then
      # 3. L3: boot web + CDP 端到端
      web_stop
      local port=$((WEB_PORT + 0))
      if web_boot "$prof" "$port"; then
        if (cd "$WEBVERIFY_DIR" && timeout 100 node l3.mjs \
            "http://127.0.0.1:$port" "Reply with exactly: OK" 40000) >> "$logf" 2>&1; then
          status="ok"
        else
          status="runtime-fail"
        fi
        web_stop
      else
        status="runtime-fail"   # web 没起来
        web_stop
      fi
    else
      status="load-fail"
    fi
  else
    status="install-fail"
  fi

  # 4. 清理临时 profile（避免污染和磁盘膨胀）
  rm -rf "$PROF_ROOT/$prof"

  log "== $name -> $status =="
  echo -e "$name\t$status"
}

main() {
  local list_file="${1:-}"
  if [ -z "$list_file" ] || [ ! -f "$list_file" ]; then
    echo "usage: $0 <list.tsv> | --one <name|src> | --continue" >&2
    exit 1
  fi

  local results="${list_file%.tsv}-results.tsv"
  local seen=""
  if [ "${2:-}" = "--continue" ]; then
    seen=$(cut -f1 "$results" 2>/dev/null | tr '\n' ' ' )
  fi

  : > "$results"
  local n=0 total=0
  total=$(wc -l < "$list_file")
  while IFS=$'\t' read -r stars name src kind; do
    [ -z "$name" ] && continue
    n=$((n+1))
    if [[ " $seen " == *" $name "* ]]; then
      echo -e "$name\tskip" >> "$results"
      continue
    fi
    log "[$n/$total]"
    echo "$(verify_one "$name" "$src")" >> "$results"
  done < "$list_file"

  log "完成。结果: $results"
  log "汇总:"
  cut -f2 "$results" | sort | uniq -c
}

# 单个插件入口
if [ "${1:-}" = "--one" ]; then
  name="${2:-}"
  [ -z "$name" ] && { echo "usage: $0 --one <name|src>" >&2; exit 1; }
  # src 可能是 npm 包名 或 github:owner/repo
  verify_one "$name" "$name"
  exit 0
fi

main "$@"
