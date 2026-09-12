#!/usr/bin/env bash
# check-ports.sh — verify the host ports ForecastGPT's compose stack wants
# are actually free.
#
# Ports checked (read from .env, all overridable in the environment):
#   REDIS_PORT       (default 6380)  — REQUIRED: the job queue.
#   API_PORT         (default 8000)  — REQUIRED: the compose api service.
#   MYSQL_HOST_PORT  (default 3306)  — WARNING ONLY: needed solely when the
#                                      optional `--profile mysql` service is
#                                      used; a busy 3306 does not stop the
#                                      app (SQLite fallback / remote DB).
#
# If a required port is bound, the script reports WHICH container/process
# holds it and says to bump the matching var in .env. It NEVER suggests
# stopping, restarting, or reusing a container it does not recognize.
#
# Usage: bash scripts/check-ports.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load port vars from .env if not already in the environment
if [ -f "$SCRIPT_DIR/../.env" ]; then
  while IFS='=' read -r k v; do
    k="$(echo "$k" | tr -d '[:space:]')"
    case "$k" in
      REDIS_PORT|API_PORT|MYSQL_HOST_PORT)
        eval "val=\"\${$k:-}\""
        [ -z "$val" ] && export "$k=$(echo "$v" | tr -d '[:space:]')"
        ;;
    esac
  done < <(grep -E '^(REDIS_PORT|API_PORT|MYSQL_HOST_PORT)=' "$SCRIPT_DIR/../.env")
fi

fail=0

# --- duplicate configured host ports ------------------------------------------
# Compose cannot bind two services to one host port; catch duplicated values
# here, before the socket checks (a duplicated-but-unbound port would
# otherwise report as "free" for both checks).
declare -A _owner_of_port
port_conflict=0
for spec in \
  "REDIS_PORT:required" \
  "API_PORT:required" \
  "MYSQL_HOST_PORT:optional"; do
  var="${spec%%:*}"
  mode="${spec##*:}"
  port="$(eval "echo \${$var:-}")"
  case "$var:$port" in
    REDIS_PORT:) port=6380 ;;
    API_PORT:) port=8000 ;;
    MYSQL_HOST_PORT:) port=3306 ;;
  esac
  if [ -n "${_owner_of_port[$port]:-}" ]; then
    other="${_owner_of_port[$port]}"
    if [ "$mode" = "required" ]; then
      echo "  [FAIL] $var and $other are BOTH set to host port $port —"
      echo "         compose cannot bind two services to one port."
      echo "         Change one of them in .env."
      fail=1
    else
      echo "  [WARN] $var ($port) collides with $other — harmless for the app,"
      echo "         but 'docker compose --profile mysql' would fail to bind."
    fi
    port_conflict=1
  fi
  _owner_of_port[$port]="$var"
done
[ "$port_conflict" -eq 1 ] && echo ""

# --- helper: is the port bound on TCP? ---------------------------------------
port_bound() {
  # Windows (netstat), then Linux (ss), then macOS (lsof) fallbacks
  if command -v netstat >/dev/null 2>&1; then
    netstat -an 2>/dev/null | grep -E "[:.]$1[[:space:]]" | grep -qiE 'LISTEN' && return 0
  fi
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | grep -q ":$1 " && return 0
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1 && return 0
  fi
  return 1
}

# --- helper: who owns the port? ----------------------------------------------
owner_of_port() {
  # Prefer docker's own view: any container publishing this host port?
  local holder
  holder="$(docker ps --filter "publish=$1" --format '{{.Names}} ({{.Image}}, {{.Ports}})' 2>/dev/null | head -3)"
  if [ -n "$holder" ]; then
    echo "$holder"
    return
  fi
  # Fall back to the OS: PID -> process name (best effort)
  local pid=""
  if command -v netstat >/dev/null 2>&1; then
    pid="$(netstat -ano 2>/dev/null | grep -E "[:.]$1[[:space:]]" | grep -i listening | awk '{print $NF}' | head -1)"
  elif command -v ss >/dev/null 2>&1; then
    pid="$(ss -ltnp 2>/dev/null | grep ":$1 " | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2)"
  fi
  if [ -n "$pid" ]; then
    local pname
    pname="$(tasklist //FI "PID eq ${pid}" //FO CSV 2>/dev/null | tail -1 | cut -d'"' -f2 \
             || ps -p "$pid" -o comm= 2>/dev/null || echo "pid $pid")"
    echo "non-docker process '${pname:-pid $pid}'"
  else
    echo "unidentified process"
  fi
}

# --- check one port: name, var, port, mode (required|optional) ----------------
check_port() {
  local name="$1" var="$2" port="$3" mode="$4"
  if port_bound "$port"; then
    echo "  $name (port $port): IN USE by:"
    echo "      $(owner_of_port "$port")"
    if [ "$mode" = "required" ]; then
      echo "    ACTION: bump $var in .env to any free port and keep dependent"
      echo "            settings (e.g. REDIS_URL) in sync."
      echo "    NOTE: do not stop or reuse the existing container/process — it"
      echo "          may belong to another project on this machine."
      fail=1
    else
      echo "    WARNING: only matters if you run 'docker compose --profile mysql'."
      echo "             If you do, bump $var in .env first. Not stopping the app."
    fi
  else
    echo "  $name (port $port): free"
  fi
}

echo "Checking host port(s) for ForecastGPT dependencies..."
check_port "Redis (job queue)"   REDIS_PORT      "${REDIS_PORT:-6380}"      required
check_port "API service"         API_PORT        "${API_PORT:-8000}"        required
check_port "MySQL (opt profile)" MYSQL_HOST_PORT "${MYSQL_HOST_PORT:-3306}" optional

echo ""
if [ "$fail" -eq 0 ]; then
  echo "OK — all required ForecastGPT dependency ports are free."
else
  echo "FAILED — resolve the conflict(s) above (change OUR port, not theirs)."
fi
exit "$fail"
