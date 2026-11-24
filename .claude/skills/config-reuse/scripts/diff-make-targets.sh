#!/usr/bin/env bash
# diff-make-targets.sh <src> <dst> [--names] — Makefile targets src has and dst lacks, with recipes, paste-ready.
# <src>/<dst> = a Makefile or a dir holding one; a missing dst Makefile counts as empty.
set -euo pipefail

names=0 args=()
for a in "$@"; do
  case "$a" in
    --names) names=1 ;;
    -*) echo "diff-make-targets: unknown flag $a" >&2; exit 2 ;;
    *) args+=("$a") ;;
  esac
done
[ "${#args[@]}" -eq 2 ] || { echo "Usage: diff-make-targets.sh <src> <dst> [--names]" >&2; exit 2; }

mk() { if [ -d "$1" ]; then printf '%s/Makefile' "$1"; else printf '%s' "$1"; fi; }
src="$(mk "${args[0]}")" dst="$(mk "${args[1]}")"
[ -f "$src" ] || { echo "diff-make-targets: no Makefile: $src" >&2; exit 1; }
[ -f "$dst" ] || dst=/dev/null

awk -v names="$names" -v dstf="$dst" '
function tname(line,   n) {
  if (!match(line, /^[A-Za-z0-9_.-]+[ \t]*:/)) return ""
  if (substr(line, RLENGTH + 1) ~ /^:?=/) return ""
  n = substr(line, 1, RLENGTH - 1); sub(/[ \t]+$/, "", n)
  return n == ".PHONY" ? "" : n
}
FILENAME == dstf { n = tname($0); if (n != "") have[n] = 1; next }
{
  n = tname($0)
  if (n != "") {
    cur = (n in have) ? "" : n
    if (cur != "") { if (names) print cur; else { if (shown++) print ""; print } }
    next
  }
  if (/^\t/) { if (cur != "" && !names) print; next }
  if (!/^[ \t]*$/) cur = ""
}' "$dst" "$src"
