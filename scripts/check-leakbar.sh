#!/usr/bin/env bash
# Leak-bar pre-push check: grep every outgoing commit (message + patch) against a
# regex term file (one ERE per line; blank and `#` lines ignored) named by the
# LOCAL git config key `leakbar.termsFile`. The term file lives outside the repo
# on purpose — a tracked list would publish the very terms it guards.
#
# Reads git's pre-push stdin: <local ref> <local sha> <remote ref> <remote sha>.
# Exit: 0 clean or skipped (key unset / file missing), 1 on any hit.
set -Eeuo pipefail

terms="$(git config --local --get leakbar.termsFile || true)"
if [[ -z "$terms" || ! -f "$terms" ]]; then
    echo "leakbar: skipped (git config leakbar.termsFile unset or file missing)" >&2
    exit 0
fi

patterns="$(mktemp)"
trap 'rm -f "$patterns"' EXIT
grep -vE '^[[:space:]]*(#|$)' "$terms" >"$patterns" || true
if [[ ! -s "$patterns" ]]; then
    echo "leakbar: skipped (term file has no patterns)" >&2
    exit 0
fi

hits=0
while read -r _lref lsha _rref rsha; do
    [[ "$lsha" =~ ^0+$ ]] && continue # branch deletion: nothing outgoing
    if [[ "$rsha" =~ ^0+$ ]] || ! git cat-file -e "$rsha^{commit}" 2>/dev/null; then
        range=("$lsha" --not --remotes) # new branch / unknown remote tip
    else
        range=("$rsha..$lsha")
    fi
    # Assignments, not pipes/process substitution: a git failure exits non-zero
    # under `set -e` (push blocked) instead of reading as "no commits, clean".
    commits="$(git rev-list "${range[@]}")"
    for c in $commits; do
        text="$(git log -1 -p --format=%B "$c")"
        out="$(grep -aiE -f "$patterns" <<<"$text" || true)"
        [[ -n "$out" ]] || continue
        subject="$(git log -1 --format='%h %s' "$c")"
        while IFS= read -r line; do
            echo "leakbar: $subject: $line" >&2
        done <<<"$out"
        hits=1
    done
done

if ((hits)); then
    echo "ERROR: outgoing commits match the leak-bar term file (above). Push blocked." >&2
    exit 1
fi
echo "leakbar: ok" >&2
