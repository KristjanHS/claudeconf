#!/bin/bash
# Ruff gate: lint keys `(code, message)` whose count grew vs the committed baseline → decision:block; format drift → additionalContext.
# Modes: none = Write|Edit (lint+format) · --lint-only = Bash write-intent dirty .py · --stop = Stop/SubagentStop re-check.

# Per-edit runs skip $skip (mid-edit states: import before use, use before import);
# --stop and any `git commit` are the done points and check every code.
mode=edit
case "${1:-}" in
  --lint-only) mode=lint ;;
  --stop) mode=stop ;;
esac
in=$(cat)
tool=$(jq -r '.tool_name // empty' <<<"$in")
sid=$(jq -r '.session_id // empty' <<<"$in" | tr -cd 'A-Za-z0-9_.-')
pending="${TMPDIR:-/tmp}/claude-ruff-pending/$sid"
skip='["F401","F811","F821","F822","F841","I001","ARG001","ARG002","ARG003","ARG004","ARG005","TC001","TC002","TC003"]'

files=()
declare -A base_rev=()
if [[ "$mode" == stop ]]; then
  [[ -n "$sid" && -s "$pending" ]] || exit 0
  # Re-entry after our own block: let the turn end; anything edited since is re-recorded.
  [[ $(jq -r '.stop_hook_active // false' <<<"$in") == true ]] && exit 0
  me=""
  if [[ $(jq -r '.hook_event_name // empty' <<<"$in") == SubagentStop ]]; then
    me=$(jq -r '.agent_id // empty' <<<"$in" | tr -cd 'A-Za-z0-9_.-')
    [[ -n "$me" ]] || exit 0
  fi
  skip='[]'
  find "${pending%/*}" -type f -mtime +7 -delete 2>/dev/null
  # Take the list atomically (appends racing this land in a fresh file); other agents' rows go back.
  taken="$pending.$$"
  mv "$pending" "$taken" 2>/dev/null || exit 0
  while IFS=$'\t' read -r p r a; do
    if [[ "$a" != "$me" ]]; then
      printf '%s\t%s\t%s\n' "$p" "$r" "$a" >>"$pending"
      continue
    fi
    [[ -n "${base_rev[$p]+x}" ]] && continue
    base_rev[$p]=$r
    [[ -f "$p" ]] || continue
    git -C "$(dirname "$p")" rev-parse --is-inside-work-tree >/dev/null 2>&1 || continue
    ((${#files[@]} < 25)) && files+=("$p")
  done <"$taken"
  rm -f "$taken"
elif [[ "$tool" == "Bash" ]]; then
  cmd=$(jq -r '.tool_input.command // empty' <<<"$in")
  [[ "$cmd" != *".py"* ]] && exit 0
  # Write-intent gate. A command that only READS a .py (grep/sed -n/cat/pytest)
  # cannot have changed it since the last Write|Edit run, so re-linting only
  # re-echoes findings the agent has already been shown. Matches the writers this
  # matcher exists to catch: redirect-to-.py (incl. heredocs), sed -i, tee, patch,
  # cp/mv/touch, and the git verbs that rewrite tracked files. `git commit` must
  # stay listed — the clean-file branch below depends on reaching it.
  grep -qE '(^|[|;&( ])(tee|patch|cp|mv|touch)([[:space:]]|$)|sed[^|;&]*[[:space:]]-[a-z]*i|>>?[[:space:]]*[A-Za-z0-9_./~-]+\.py|git[[:space:]]+(commit|checkout|restore|apply|stash|merge|rebase|pull)' <<<"$cmd" || exit 0
  [[ "$cmd" == *"git commit"* ]] && skip='[]'
  cwd=$(jq -r '.cwd // empty' <<<"$in")
  while read -r tok; do
    p="${tok/#\~/$HOME}"
    [[ "$p" == /* ]] || p="$cwd/$p"
    [[ -f "$p" ]] || continue
    d=$(dirname "$p")
    # Repo files only (skips non-repo scratch), and only if git-dirty — OR the command
    # commits (a write+commit chain leaves the file clean by hook time, the exact
    # bypass this matcher exists to close). Known accepted false positive: a dirty
    # WIP file with lint errors blocks even pure-read/execute mentions of it.
    git -C "$d" rev-parse --is-inside-work-tree >/dev/null 2>&1 || continue
    if [[ -z $(git -C "$d" status --porcelain -- "$p" 2>/dev/null) ]]; then
      [[ "$cmd" == *"git commit"* ]] || continue
    fi
    files+=("$p")
    ((${#files[@]} >= 10)) && break
  done < <(grep -oE '[A-Za-z0-9_./~-]+\.py\b' <<<"$cmd" | sort -u)
else
  f=$(jq -r '.tool_input.file_path // empty' <<<"$in")
  [[ -n "$f" && "$f" == *.py ]] && files+=("$f")
fi
((${#files[@]})) || exit 0

# Record `path<TAB>HEAD now<TAB>agent_id`; --stop lints each path vs its FIRST row's rev, so a mid-session commit can't hide a finding.
if [[ "$mode" != stop && -n "$sid" ]]; then
  aid=$(jq -r '.agent_id // empty' <<<"$in" | tr -cd 'A-Za-z0-9_.-')
  mkdir -p "${pending%/*}" 2>/dev/null && for p in "${files[@]}"; do
    printf '%s\t%s\t%s\n' "$p" "$(git -C "$(dirname "$p")" rev-parse -q --verify HEAD 2>/dev/null)" "$aid"
  done >>"$pending"
fi

# Lint findings in $1 (ruff JSON) whose (code, message) count grew vs $2, as concise lines.
# Codes in $skip are dropped first (`invalid-syntax` is never in it).
new_findings() {
  # --slurpfile, not --argjson: a legacy file's JSON overruns the 128 KiB per-argv cap.
  jq -rn --argjson skip "$skip" --slurpfile n <(printf %s "$1") --slurpfile o <(printf %s "$2") '
    def k: [.code, .message] | tojson;
    ($n[0] | map(select(.code as $c | any($skip[]; . == $c) | not))) as $now | $o[0] as $base
    | ($base | map(k) | group_by(.) | map({key: .[0], value: length}) | from_entries) as $b
    | [$now | group_by(k)[] | select(length > ($b[.[0] | k] // 0))[]]
    | sort_by(.location.row, .location.column)[]
    | "\(.filename):\(.location.row):\(.location.column): \(.code) \(.message)"'
}

nl=$'\n\n'
ctx=""
fctx=""
for f in "${files[@]}"; do
  # Prefer the file's uv-locked project ruff (version-matches CI); fall back to host ruff.
  ruff=(ruff)
  d=$(dirname "$f")
  while [[ "$d" == /* && "$d" != "/" ]]; do
    if [[ -f "$d/uv.lock" ]] && grep -q '^name = "ruff"$' "$d/uv.lock" && command -v uv >/dev/null 2>&1; then
      ruff=(uv run --frozen --project "$d" ruff)
      break
    fi
    d=$(dirname "$d")
  done
  # Baseline = HEAD's copy; a Bash-path file that is git-clean was just committed, so use the
  # parent of the last commit touching it. Untracked / no repo ⇒ no baseline ⇒ every finding reports.
  d=$(dirname "$f")
  b=$(basename "$f")
  rev=HEAD
  if [[ "$mode" == stop ]]; then
    rev=${base_rev[$f]}
  elif [[ "$tool" == "Bash" && -z $(git -C "$d" status --porcelain -- "$b" 2>/dev/null) ]]; then
    rev="$(git -C "$d" log -1 --format=%H -- "$b" 2>/dev/null)~1"
  fi
  has_base=0
  [[ -n "$rev" ]] && git -C "$d" cat-file -e "$rev:./$b" 2>/dev/null && has_base=1

  now=$("${ruff[@]}" check --output-format json "$f" 2>/dev/null)
  base='[]'
  ((has_base)) && base=$(git -C "$d" show "$rev:./$b" | "${ruff[@]}" check --output-format json --stdin-filename "$f" - 2>/dev/null)
  if lint=$(new_findings "$now" "$base" 2>/dev/null); then
    [[ -n "$lint" ]] && ctx="${ctx}${ctx:+$nl}$lint"
  else
    # ruff errored (no JSON): fall back to the raw concise report.
    lint=$("${ruff[@]}" check --output-format concise "$f" 2>&1) || ctx="${ctx}${ctx:+$nl}$lint"
  fi

  [[ "$mode" == edit ]] || continue
  if ! fmt=$("${ruff[@]}" format --check "$f" 2>&1); then
    if ! ((has_base)) || git -C "$d" show "$rev:./$b" | "${ruff[@]}" format --check --stdin-filename "$f" - >/dev/null 2>&1; then
      fctx="${fctx}${fctx:+$nl}[ruff format --check] $fmt"
    fi
  fi
done

if [[ "$mode" == stop && -n "$ctx" ]]; then
  ctx="ruff, end of turn: new findings in files edited this session (per-edit runs skip mid-edit codes like F401/F821). Reported once — fix, or keep deliberately:${nl}$ctx"
fi
if [[ -n "$ctx" || -n "$fctx" ]]; then
  jq -n --arg r "$ctx" --arg f "$fctx" '
    (if $r != "" then {decision: "block", reason: $r} else {} end)
    + (if $f != "" then {hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $f}} else {} end)'
fi
exit 0
