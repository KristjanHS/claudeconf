#!/usr/bin/env bash
# diff-configs.sh — Compare source project configs against global and current project
# Usage: diff-configs.sh <SOURCE_PROJECT_PATH> [CURRENT_PROJECT_PATH]
# Output: TSV — TYPE  REL_PATH  STATUS  MATCH_PATH

set -euo pipefail

SOURCE="${1:-}"
CURRENT="${2:-$(pwd)}"
GLOBAL="$HOME/.claude"

[[ -z "$SOURCE" ]] && { echo "Usage: diff-configs.sh /path/to/source [/path/to/target]" >&2; exit 1; }
SOURCE="$(realpath "$SOURCE")"
CURRENT="$(realpath "$CURRENT")"
[[ -d "$SOURCE" ]] || { echo "ERROR: Not a directory: $SOURCE" >&2; exit 1; }

printf 'TYPE\tREL_PATH\tSTATUS\tMATCH_PATH\n'

md5of() { [[ -f "$1" ]] && md5sum "$1" 2>/dev/null | cut -d' ' -f1 || echo MISSING; }

# Map source config → global equivalent (empty = no global equivalent)
global_of() {
  local type="$1" rel="$2"
  case "$type" in
    command) echo "$GLOBAL/commands/${rel#.claude/commands/}" ;;
    skill)   echo "$GLOBAL/skills/${rel#.claude/skills/}" ;;
    claude_md)
      [[ "$rel" == "CLAUDE.local.md" ]] && echo "" || echo "$GLOBAL/CLAUDE.md" ;;
    *) echo "" ;;
  esac
}

compare() {
  local src="$1" type="$2" rel="$3"
  local src_md5 gp pp

  src_md5=$(md5of "$src")
  gp=$(global_of "$type" "$rel")
  pp="$CURRENT/$rel"

  # Check global match
  if [[ -n "$gp" && -f "$gp" ]] && [[ "$(md5of "$gp")" == "$src_md5" ]]; then
    printf '%s\t%s\t%s\t%s\n' "$type" "$rel" "identical_global" "$gp"; return
  fi
  # Check project match (skip if same dir)
  if [[ "$CURRENT" != "$SOURCE" && -f "$pp" ]] && [[ "$(md5of "$pp")" == "$src_md5" ]]; then
    printf '%s\t%s\t%s\t%s\n' "$type" "$rel" "identical_project" "$pp"; return
  fi
  # Exists but differs
  if [[ -n "$gp" && -f "$gp" ]]; then
    printf '%s\t%s\t%s\t%s\n' "$type" "$rel" "differs_global" "$gp"; return
  fi
  if [[ "$CURRENT" != "$SOURCE" && -f "$pp" ]]; then
    printf '%s\t%s\t%s\t%s\n' "$type" "$rel" "differs_project" "$pp"; return
  fi
  # Not installed anywhere
  printf '%s\t%s\t%s\t%s\n' "$type" "$rel" "not_installed" "-"
}

# Walk source configs (same order as scan-configs.sh)
for f in CLAUDE.md CLAUDE.local.md; do
  [[ -f "$SOURCE/$f" ]] && compare "$SOURCE/$f" claude_md "$f"
done
[[ -f "$SOURCE/.claude/CLAUDE.md" ]] && compare "$SOURCE/.claude/CLAUDE.md" claude_md ".claude/CLAUDE.md"
[[ -f "$SOURCE/.claudeignore" ]] && compare "$SOURCE/.claudeignore" claudeignore ".claudeignore"

if [[ -d "$SOURCE/.claude/rules" ]]; then
  for f in "$SOURCE/.claude/rules/"*.md; do
    [[ -f "$f" ]] || continue
    compare "$f" rule ".claude/rules/$(basename "$f")"
  done
fi

if [[ -d "$SOURCE/.claude/commands" ]]; then
  while IFS= read -r -d '' f; do
    compare "$f" command "${f#"$SOURCE/"}"
  done < <(find "$SOURCE/.claude/commands" -name "*.md" -type f -print0 | sort -z)
fi

if [[ -d "$SOURCE/.claude/skills" ]]; then
  while IFS= read -r -d '' f; do
    compare "$f" skill "${f#"$SOURCE/"}"
  done < <(find "$SOURCE/.claude/skills" -name "SKILL.md" -type f -print0 | sort -z)
fi
