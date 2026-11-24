#!/usr/bin/env bash
# rank-sources.sh [TARGET_PATH] [--top N] — rank $PROJECTS_DIR repos as config sources for TARGET (default: cwd).
# Output: TSV — SCORE  PATH  MARKERS, best first.
set -euo pipefail

# shellcheck source=lib-projects.sh source-path=SCRIPTDIR
source "$(dirname "${BASH_SOURCE[0]}")/lib-projects.sh"

TARGET="$(pwd)" TOP=10
while [ $# -gt 0 ]; do
  case "$1" in
    --top) TOP="$2"; shift 2 ;;
    -*) echo "rank-sources: unknown flag $1" >&2; exit 2 ;;
    *) TARGET="$1"; shift ;;
  esac
done
TARGET="$(realpath "$TARGET")"

# file:weight — doubled when the target carries the same marker.
MARKERS=(pyproject.toml:3 uv.lock:2 Makefile:2 .pre-commit-config.yaml:2 Dockerfile:1 .gitmodules:1)

score() {
  local p="$1" s=0 spec f w found=()
  for spec in "${MARKERS[@]}"; do
    f="${spec%:*}" w="${spec##*:}"
    [[ -e "$p/$f" ]] || continue
    [[ -e "$TARGET/$f" ]] && w=$((w * 2))
    s=$((s + w)); found+=("$f")
  done
  for f in rules skills; do
    if [[ -n "$(ls -A "$p/.claude/$f" 2>/dev/null)" ]]; then s=$((s + 2)); found+=(".claude/$f"); fi
  done
  local IFS=,
  printf '%s\t%s\t%s\n' "$s" "$p" "${found[*]:-none}"
}

printf 'SCORE\tPATH\tMARKERS\n'
while IFS= read -r p; do score "$p"; done < <(list_projects "$TARGET") \
  | sort -t $'\t' -k1,1nr -k2,2 | awk -v n="$TOP" 'NR <= n'
