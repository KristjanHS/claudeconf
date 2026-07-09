#!/usr/bin/env bash
# BLOCKING identity/PII gate for the public claudeconf repo.
#
# Unlike the advisory original in the author's private dotfiles (which exits 0
# and only warns, because dotfiles legitimately pins some absolute paths), ANY
# hit here FAILS the commit: a public teaching repo has no legitimate reason to
# ship an absolute home path or a personal email address. gitleaks catches
# *credentials*; this catches *identity/PII leakage*, the dominant risk for a
# repo whose whole purpose is to be copied by strangers.
#
# Patterns are GENERIC on purpose. The private design sketch suggested baking
# the author's literal email/username into this file, but that would re-leak the
# exact identity we are scrubbing into a public repo. Generic category patterns
# (any /home/<user>/ path, any email address) catch the same leaks without
# shipping anyone's name.
set -Eeuo pipefail

here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
allowlist="$here/hardcoded-paths-allowlist.txt"

exclusions=()
if [ -f "$allowlist" ]; then
    while IFS= read -r line; do
        line="${line%%#*}"                       # strip inline comments
        line="${line#"${line%%[![:space:]]*}"}"  # ltrim
        line="${line%"${line##*[![:space:]]}"}"  # rtrim
        [ -z "$line" ] && continue
        exclusions+=(":(exclude)$line")
    done < "$allowlist"
fi

# Categories that must never appear in tracked files:
#   - absolute home paths:  /home/<user>/  or  /Users/<user>/
#   - any email address
patterns=(
    '/home/[A-Za-z0-9._-]+/'
    '/Users/[A-Za-z0-9._-]+/'
    '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
)

# This script and its allowlist legitimately *describe* the patterns, so exclude
# them from their own scan to avoid self-matching.
self_exclusions=(
    ':(exclude)scripts/check-hardcoded-paths.sh'
    ':(exclude)scripts/hardcoded-paths-allowlist.txt'
    ':(exclude).gitleaksignore'
)

hits=""
for pat in "${patterns[@]}"; do
    # --cached: scan the INDEX (what will actually be committed), not the
    # working tree — otherwise a `git add`-then-edit could slip PII past the
    # pre-commit gate. Manual full-tree runs `git add -A` first.
    found=$(git grep --cached -nIE "$pat" -- \
        "${self_exclusions[@]}" "${exclusions[@]}" 2>/dev/null || true)
    [ -n "$found" ] && hits+="$found"$'\n'
done

if [ -n "${hits//[$'\n']/}" ]; then
    echo "ERROR: identity/PII leakage detected — sanitize before committing:" >&2
    echo "$hits" >&2
    echo "  Replace /home/<user>/ with \$HOME or ~ ; remove personal emails." >&2
    echo "  Genuine, documented exceptions: scripts/hardcoded-paths-allowlist.txt" >&2
    exit 1
fi

echo "ok: no identity/PII leakage in tracked files"
