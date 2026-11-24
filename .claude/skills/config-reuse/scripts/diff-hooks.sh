#!/usr/bin/env bash
# diff-hooks.sh <repo>... — every hook layer that fires in each repo, to diff source vs target.
# Output: TSV — LAYER(precommit|git|claude)  SCOPE(repo|global|session)  NAME  ORIGIN
set -euo pipefail

[ $# -ge 1 ] || { echo "Usage: diff-hooks.sh <repo>..." >&2; exit 2; }

printf 'LAYER\tSCOPE\tNAME\tORIGIN\n'
{
  for repo in "$@"; do
    repo="$(realpath "$repo")"
    pc="$repo/.pre-commit-config.yaml"
    if [ -f "$pc" ]; then
      sed -n 's/^[[:space:]]*- id:[[:space:]]*\([^[:space:]#]*\).*/\1/p' "$pc" |
        while IFS= read -r id; do printf 'precommit\trepo\t%s\t%s\n' "$id" "$pc"; done
    fi
    common="$(git -C "$repo" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || continue
    { git -C "$repo" config --show-origin --get-regexp '^hook\.|^core\.hookspath$' || true; } |
      while IFS=$'\t' read -r origin kv; do
        origin="${origin#file:}"
        [[ "$origin" == /* ]] || origin="$repo/$origin"
        scope=global; [ "$origin" = "$common/config" ] && scope=repo
        key="${kv%% *}"
        case "$key" in
          hook.*) name="${key#hook.}"; name="${name%.*}" ;;
          *) name="core.hooksPath=${kv#* }" ;;
        esac
        printf 'git\t%s\t%s\t%s\n' "$scope" "$name" "$origin"
      done
  done
  settings="$HOME/.claude/settings.json"
  # `if`, not `[ -f ] &&`: as the group's last command a false test would exit 1 under pipefail
  if [ -f "$settings" ]; then
    jq -r '.hooks // {} | .. | .command? // empty' "$settings" |
      while IFS= read -r cmd; do printf 'claude\tsession\t%s\t%s\n' "$cmd" "$settings"; done
  fi
} | awk '!seen[$0]++'
