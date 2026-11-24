#!/usr/bin/env bash
# find-dup-hooks.sh — after promoting a hook to global, list per-project pre-commit ids it now duplicates.
# A pre-commit id duplicates a global git hook when it equals that hook's stem (`<stem>-commit|-push`).
# Read-only: never edits a project. Output: TSV — PROJECT  HOOK_ID  GLOBAL_HOOK
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib-projects.sh source-path=SCRIPTDIR
. "$here/lib-projects.sh"

printf 'PROJECT\tHOOK_ID\tGLOBAL_HOOK\n'
list_projects | while IFS= read -r p; do
  bash "$here/diff-hooks.sh" "$p" | awk -F'\t' -v p="$p" '
    $1 == "git" && $2 == "global" && $3 ~ /-(commit|push)$/ {
      stem = $3; sub(/-(commit|push)$/, "", stem); global[stem] = global[stem] ? global[stem] "," $3 : $3
    }
    $1 == "precommit" { ids[++n] = $3 }
    END { for (i = 1; i <= n; i++) if (ids[i] in global) printf "%s\t%s\t%s\n", p, ids[i], global[ids[i]] }
  '
done
