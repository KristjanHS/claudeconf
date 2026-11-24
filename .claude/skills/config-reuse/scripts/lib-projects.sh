#!/usr/bin/env bash
# lib-projects.sh — sourced; list_projects [TARGET] prints candidate source repos, one realpath per line.

list_projects() {
  local target="${1:-}" d base
  [[ -n "$target" ]] && target="$(realpath "$target")"
  for d in "${PROJECTS_DIR:-$HOME/projects}"/*/; do
    d="${d%/}"
    base="${d##*/}"
    case "$base" in *pre-fold*|*-wt|*-private) continue ;; esac
    [[ -e "$d/.git" ]] || continue
    d="$(realpath "$d")"
    [[ "$d" == "$target" ]] && continue
    printf '%s\n' "$d"
  done
}
