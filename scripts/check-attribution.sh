#!/usr/bin/env bash
# Fails when the text on stdin (commit messages, a PR title/body) carries
# AI-tool attribution: a co-author trailer naming an AI tool, or a
# "generated with <tool>" footer. Product mentions such as "reports
# generated with Gemini" stay allowed: Gemini is the app's LLM backend.
#
# Used by the attribution-guard CI job and the optional commit-msg hook
# (git config core.hooksPath scripts/hooks). Policy: CONTRIBUTING.md.
set -uo pipefail

pattern='co-authored-by:.*(claude|anthropic|copilot|chatgpt|openai|gemini|cursor)|generated (with|by) \[?(claude|chatgpt|copilot|cursor)'

hits=$(grep -Ein "$pattern" || true)
if [ -n "$hits" ]; then
  echo "AI attribution found; remove it (CONTRIBUTING.md, Attribution):" >&2
  echo "$hits" >&2
  exit 1
fi
