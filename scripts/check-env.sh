#!/usr/bin/env bash
# check-env.sh — fail LOUDLY on missing/invalid required configuration instead
# of the app misbehaving silently at runtime.
#
# Checks:
#   1. .env exists (with .env.example as the template)
#   2. no real-looking secret is tracked in git (quick literal scan)
#   3. LLM_PROVIDER / EMBEDDING_PROVIDER values are known
#   4. the selected providers' required keys are present and non-placeholder
#   5. REDIS_PORT is set
#
# Usage: bash scripts/check-env.sh   (run from the repo root or anywhere)
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$SCRIPT_DIR/.."
fail=0

err() { echo "  [FAIL] $*"; fail=1; }
ok()  { echo "  [ok]   $*"; }

echo "ForecastGPT environment check ($ROOT)"

# --- 1. .env presence ---------------------------------------------------------
if [ -f "$ROOT/.env" ]; then
  ok ".env exists"
else
  echo "  [FAIL] .env not found. Create it from the template:"
  echo "           cp .env.example .env   # then edit"
  fail=1
fi

# --- load .env (do not override already-exported vars) ------------------------
if [ -f "$ROOT/.env" ]; then
  # shellcheck disable=SC1091
  set -a; source "$ROOT/.env"; set +a
fi

# --- 2. no tracked secret literals --------------------------------------------
leaks="$(git -C "$ROOT" ls-files -z 2>/dev/null | xargs -0 grep -lE \
  '(sk-[A-Za-z0-9]{20,}|fgpt_[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{30,})' 2>/dev/null | head -5)"
if [ -n "$leaks" ]; then
  err "possible real API keys tracked in git: $leaks"
else
  ok "no secret-looking literals in tracked files"
fi

# --- 3. providers known --------------------------------------------------------
llm="${LLM_PROVIDER:-ollama}"
emb="${EMBEDDING_PROVIDER:-ollama}"
case "$llm" in
  ollama|openai|anthropic) ok "LLM_PROVIDER=$llm" ;;
  *) err "LLM_PROVIDER='$llm' is not one of: ollama | openai | anthropic" ;;
esac
case "$emb" in
  ollama|openai) ok "EMBEDDING_PROVIDER=$emb" ;;
  *) err "EMBEDDING_PROVIDER='$emb' is not one of: ollama | openai" ;;
esac

# --- 4. keys for the selected providers ----------------------------------------
placeholder_re='(your[-_]|<|example|changeme|xxx)'
check_key() { # name, value, needed_by
  local name="$1" val="$2" who="$3"
  if [ -z "$val" ]; then
    err "$name is empty but $who requires it"
  elif echo "$val" | grep -qiE "$placeholder_re"; then
    err "$name looks like a placeholder — set a real value for $who"
  else
    ok "$name is set for $who"
  fi
}

if [ "$llm" = "openai" ] || [ "$emb" = "openai" ]; then
  check_key "OPENAI_API_KEY" "${OPENAI_API_KEY:-}" "the openai provider"
fi
if [ "$llm" = "anthropic" ]; then
  check_key "ANTHROPIC_API_KEY" "${ANTHROPIC_API_KEY:-}" "the anthropic provider"
fi

# --- 5. REDIS_PORT --------------------------------------------------------------
if [ -n "${REDIS_PORT:-}" ]; then
  ok "REDIS_PORT=$REDIS_PORT"
else
  err "REDIS_PORT is not set (checked-in default is 6380 — never assume 6379 is free)"
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "OK — environment is coherent."
  exit 0
else
  echo "FAILED — fix the [FAIL] items above before starting the app."
  exit 1
fi
