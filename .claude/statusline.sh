#!/bin/bash
# Status line for Claude Code: model, context %, distance-to-session-stop, cost, 5h limit.
# Context window is pinned to 200k (a personal session budget), not the real 1M.
# Stop cliff at 75% = 150k tokens — the point to /clear or wrap up, well before the
# native autocompact trigger (75% of 1M = 750k) ever fires.
#
# Portable: needs only `jq` + `git`. Reads Claude Code's statusline JSON on stdin.
# The 130k yellow / 160k red marks are shared with .claude/hooks/impag-budget-check.py
# (its 130k wrap-up threshold) so the visual warning and the automated /impag
# wrap-up fire off the same point.

input=$(cat)

MODEL=$(echo "$input"  | jq -r '.model.display_name // "?"')
USED_TOK=$(echo "$input" | jq -r '((.context_window.current_usage.input_tokens // 0) + (.context_window.current_usage.cache_creation_input_tokens // 0) + (.context_window.current_usage.cache_read_input_tokens // 0))')
COST=$(echo "$input"   | jq -r '.cost.total_cost_usd // 0')
FIVE_H=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
CWD=$(echo "$input"    | jq -r '.workspace.current_dir // .cwd // empty')
BRANCH=$(git -C "${CWD:-.}" branch --show-current 2>/dev/null)
PROJ=$(basename "${CWD:-}")

# Pinned to 200k session-stop budget. Cliff at 75% = 150k tokens.
WINDOW=200000
STOP_PCT=75
PCT=$((USED_TOK * 100 / WINDOW))
REMAIN_TO_STOP=$((WINDOW * STOP_PCT / 100 - USED_TOK))

# Color by urgency (raw-token thresholds: yellow at 130k, red at 160k)
GREEN='\033[32m'; YELLOW='\033[33m'; RED='\033[31m'; DIM='\033[2m'; RESET='\033[0m'
if   [ "$USED_TOK" -ge 160000 ]; then COLOR="$RED"
elif [ "$USED_TOK" -ge 130000 ]; then COLOR="$YELLOW"
else                                  COLOR="$GREEN"; fi

# Progress bar (10 chars)
FILLED=$((PCT / 10)); EMPTY=$((10 - FILLED))
printf -v F "%${FILLED}s"; printf -v E "%${EMPTY}s"
BAR="${F// /█}${PAD:-${E// /░}}"

COST_FMT=$(printf '$%.2f' "$COST")

# Warn when close to session stop (within 20k tokens = 10% of 200k)
if [ "$REMAIN_TO_STOP" -le 20000 ]; then
  WARN=" ${RED}← /clear soon${RESET}"
else
  WARN=""
fi

LIMIT_SEG=""
[ -n "$FIVE_H" ] && LIMIT_SEG=" ${DIM}| 5h: $(printf '%.0f' "$FIVE_H")%${RESET}"

# Format used tokens compactly: "120k" for ≥1k, else raw
if [ "$USED_TOK" -ge 1000 ]; then
  USED_FMT="$((USED_TOK / 1000))k"
else
  USED_FMT="$USED_TOK"
fi

REPO_SEG=""
if [ -n "$PROJ" ] && [ -n "$BRANCH" ]; then
  REPO_SEG=" ${DIM}${PROJ} [${BRANCH}]${RESET}"
elif [ -n "$PROJ" ]; then
  REPO_SEG=" ${DIM}${PROJ}${RESET}"
fi

printf '%b\n' "[${MODEL}] ${COLOR}${BAR}${RESET} ${PCT}% ${DIM}(${USED_FMT} tok)${RESET}${REPO_SEG}${WARN} ${DIM}| ${COST_FMT}${RESET}${LIMIT_SEG}"
