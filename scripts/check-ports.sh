#!/usr/bin/env bash
# check-ports.sh — verify the host ports ForecastGPT wants are actually free.
#
# Reads REDIS_PORT from .env (default 6380 — this repo never assumes 6379).
# If a port is already bound, it reports WHICH container/process holds it and
# tells you to bump REDIS_PORT in .env. It NEVER suggests stopping, restarting,
# or reusing a container it does not recognize.
#
# Usage: bash scripts/check-ports.sh
set -uo pipefail

PORT="${REDIS_PORT:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load REDIS_PORT from .env if not already in the environment
if [ -z "$PORT" ] && [ -f "$SCRIPT_DIR/../.env" ]; then
  PORT="$(grep -E '^REDIS_PORT=' "$SCRIPT_DIR/../.env" | tail -1 | cut -d= -f2 | tr -d '[:space:]')"
fi
PORT="${PORT:-6380}"

echo "Checking host port(s) for ForecastGPT dependencies..."
echo "  REDIS_PORT = $PORT"

fail=0

# --- helper: is the port bound on TCP? ---------------------------------------
port_bound() {
  # Windows (netstat), then Linux (ss), then macOS (lsof) fallbacks
  if command -v netstat >/dev/null 2>&1; then
    netstat -an 2>/dev/null | grep -E "[:.]${PORT}[[:space:]]" | grep -qiE 'LISTEN' && return 0
  fi
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | grep -q ":${PORT} " && return 0
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1 && return 0
  fi
  return 1
}

# --- helper: who owns the port? ----------------------------------------------
owner_of_port() {
  # Prefer docker's own view: any container publishing this host port?
  local holder
  holder="$(docker ps --filter "publish=${PORT}" --format '{{.Names}} ({{.Image}}, {{.Ports}})' 2>/dev/null | head -3)"
  if [ -n "$holder" ]; then
    echo "$holder"
    return
  fi
  # Fall back to the OS: PID -> process name (best effort)
  local pid=""
  if command -v netstat >/dev/null 2>&1; then
    pid="$(netstat -ano 2>/dev/null | grep -E "[:.]${PORT}[[:space:]]" | grep -i listening | awk '{print $NF}' | head -1)"
  elif command -v ss >/dev/null 2>&1; then
    pid="$(ss -ltnp 2>/dev/null | grep ":${PORT} " | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2)"
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

# --- check -------------------------------------------------------------------
if port_bound; then
  echo ""
  echo "  PORT $PORT IS ALREADY IN USE by:"
  echo "    $(owner_of_port)"
  echo ""
  echo "  ACTION: bump REDIS_PORT in .env to any free port (e.g. $((PORT + 1)))"
  echo "          and keep REDIS_URL in sync (redis://localhost:<port>/0)."
  echo "  NOTE: do not stop or reuse the existing container/process — it may"
  echo "        belong to another project on this machine."
  fail=1
else
  echo "  port $PORT: free"
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "OK — all ForecastGPT dependency ports are free."
else
  echo "FAILED — resolve the conflict(s) above (change OUR port, not theirs)."
fi
exit "$fail"
