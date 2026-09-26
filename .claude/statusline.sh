#!/bin/bash
# Status line for Claude Code: model, context %, distance-to-session-stop, cost, 5h + 7d limits.
# Context window is pinned to 300k (user's personal session budget), not the real 1M.
# Stop cliff at 75% = 225k tokens — the point to /clear or wrap up, well before the
# native autocompact trigger (75% of 1M = 750k) ever fires.

input=$(cat)

MODEL=$(echo "$input"  | jq -r '.model.display_name // "?"' | sed -E 's/ *\([^)]*context[^)]*\)//I')
USED_TOK=$(echo "$input" | jq -r '((.context_window.current_usage.input_tokens // 0) + (.context_window.current_usage.cache_creation_input_tokens // 0) + (.context_window.current_usage.cache_read_input_tokens // 0))')
COST=$(echo "$input"   | jq -r '.cost.total_cost_usd // 0')
FIVE_H=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
SEVEN_D=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')
CWD=$(echo "$input"    | jq -r '.workspace.current_dir // .cwd // empty')
BRANCH=$(git -C "${CWD:-.}" branch --show-current 2>/dev/null)
# Display-only squeeze: `claudesec` names its branches `worktree-<name>`, which eats
# status-line width. The real branch keeps the long name — only the label shortens.
BRANCH=${BRANCH/#worktree-/wt-}
# In a linked worktree (`claudesec`) the CWD basename is the worktree NAME — `sec`
# under `<repo>-wt/` — so derive the label from the PRIMARY checkout: the first
# `git worktree list` entry, the same resolution `claudesec`/`wt-resolve` use
# (correct from the primary and from any linked sibling, and submodule-safe unlike
# `--git-common-dir`). The worktree identity is not lost — it rides in the branch
# (`worktree-sec`).
PRIMARY=$(git -C "${CWD:-.}" worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2; exit}')
PROJ=$(basename "${PRIMARY:-${CWD:-}}")

# Pinned to 300k session-stop budget. Cliff at 75% = 225k tokens.
WINDOW=300000
STOP_PCT=75
PCT=$((USED_TOK * 100 / WINDOW))
REMAIN_TO_STOP=$((WINDOW * STOP_PCT / 100 - USED_TOK))

# Color by urgency (raw-token thresholds: yellow at 200k, red at 240k)
GREEN='\033[32m'; YELLOW='\033[33m'; RED='\033[31m'; DIM='\033[2m'; RESET='\033[0m'
if   [ "$USED_TOK" -ge 240000 ]; then COLOR="$RED"
elif [ "$USED_TOK" -ge 200000 ]; then COLOR="$YELLOW"
else                                  COLOR="$GREEN"; fi

# Progress bar (10 chars)
FILLED=$((PCT / 10)); EMPTY=$((10 - FILLED))
printf -v F "%${FILLED}s"; printf -v E "%${EMPTY}s"
BAR="${F// /█}${PAD:-${E// /░}}"

COST_FMT=$(printf '$%.2f' "$COST")

# Warn when close to session stop (within 30k tokens = 10% of 300k)
if [ "$REMAIN_TO_STOP" -le 30000 ]; then
  WARN=" ${RED}← /clear soon${RESET}"
else
  WARN=""
fi

LIMIT_SEG=""
[ -n "$FIVE_H" ]  && LIMIT_SEG="${LIMIT_SEG} | 5h:$(printf '%.0f' "$FIVE_H")%"
[ -n "$SEVEN_D" ] && LIMIT_SEG="${LIMIT_SEG} | 7d:$(printf '%.0f' "$SEVEN_D")%"
[ -n "$LIMIT_SEG" ] && LIMIT_SEG="${DIM}${LIMIT_SEG}${RESET}"

# Format used tokens compactly: "120k" for ≥1k, else raw
if [ "$USED_TOK" -ge 1000 ]; then
  USED_FMT="$((USED_TOK / 1000))k"
else
  USED_FMT="$USED_TOK"
fi

REPO_SEG=""
if [ -n "$PROJ" ] && [ -n "$BRANCH" ]; then
  REPO_SEG=" ${DIM}${PROJ}[${BRANCH}]${RESET}"
elif [ -n "$PROJ" ]; then
  REPO_SEG=" ${DIM}${PROJ}${RESET}"
fi

printf '%b\n' "[${MODEL}] ${COLOR}${BAR}${RESET} ${PCT}% ${DIM}(${USED_FMT})${RESET}${REPO_SEG}${WARN} ${DIM}| ${COST_FMT}${RESET}${LIMIT_SEG}"
