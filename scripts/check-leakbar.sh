#!/usr/bin/env bash
# Leak-bar pre-push check: grep every outgoing commit (message, author/committer
# identity, patch) and annotated tag against a regex term file (one ERE per line;
# blank and `#` lines ignored) named by the LOCAL git config key
# `leakbar.termsFile`. The term file lives outside the repo on purpose — a
# tracked list would publish the very terms it guards.
#
# Usage: check-leakbar.sh [<remote name>]  (pre-push hook passes its $1).
# Reads git's pre-push stdin: <local ref> <local sha> <remote ref> <remote sha>.
# Exit: 0 clean or skipped (key unset / file missing), 1 on any hit, 2 on a
# scan error (bad regex, unreadable term file, git config failure).
set -Eeuo pipefail

die() {
    echo "leakbar: $*. Push blocked." >&2
    exit 2
}

# grep, but only rc 1 (no match) counts as clean; rc >=2 is a bad regex or read
# error, which `|| true` would turn into a silent pass.
scan() {
    local rc=0
    grep "$@" || rc=$?
    ((rc <= 1)) || die "grep failed (rc $rc)"
}

rc=0
terms="$(git config --local --get leakbar.termsFile)" || rc=$?
((rc <= 1)) || die "git config --get leakbar.termsFile failed (rc $rc)"
if [[ -z "$terms" || ! -f "$terms" ]]; then
    echo "leakbar: skipped (git config leakbar.termsFile unset or file missing)" >&2
    exit 0
fi

patterns="$(mktemp)"
trap 'rm -f "$patterns"' EXIT
scan -vE '^[[:space:]]*(#|$)' "$terms" >"$patterns"
if [[ ! -s "$patterns" ]]; then
    echo "leakbar: skipped (term file has no patterns)" >&2
    exit 0
fi
scan -aiE -f "$patterns" </dev/null # compile once: a bad ERE fails here, not per commit

# Exclude only what the push target already has; a URL / unknown remote gets no
# exclusion — over-scanning is safe, skipping a private remote's commits is not.
remote="${1:-}"
exclude=()
if [[ -n "$remote" ]] && git config --get "remote.$remote.url" >/dev/null 2>&1; then
    exclude=(--not --remotes="$remote")
fi

hits=0
report() { # <label> <matched lines>
    while IFS= read -r line; do
        echo "leakbar: $1: $line" >&2
    done <<<"$2"
    hits=1
}

while read -r lref lsha _rref rsha; do
    [[ "$lsha" =~ ^0+$ ]] && continue # branch deletion: nothing outgoing
    if [[ "$(git cat-file -t "$lsha")" == tag ]]; then
        out="$(scan -aiE -f "$patterns" <<<"$(git cat-file tag "$lsha")")"
        [[ -z "$out" ]] || report "tag $lref" "$out"
    fi
    if [[ "$rsha" =~ ^0+$ ]] || ! git cat-file -e "$rsha^{commit}" 2>/dev/null; then
        range=("$lsha" "${exclude[@]}") # new branch / unknown remote tip
    else
        range=("$rsha..$lsha")
    fi
    # Assignments, not pipes/process substitution: a git failure exits non-zero
    # under `set -e` (push blocked) instead of reading as "no commits, clean".
    commits="$(git rev-list "${range[@]}")"
    for c in $commits; do
        # Added lines + new names only: a removed/context line came from an earlier commit,
        # already pushed or flagged where it was added — scrub commits must pass.
        meta="$(git log -1 --no-color --format='%an %ae%n%cn %ce%n%B' "$c")"
        # --text/--no-textconv/--no-ext-diff/--no-color: `-diff`, textconv and color
        # config must not hide or prefix the raw `+` lines.
        patch="$(git show --format= -p -M --text --no-textconv --no-ext-diff --no-color "$c")"
        added="$(scan -aE '^(\+|rename to |copy to )' <<<"$patch")"
        out="$(scan -aiE -f "$patterns" <<<"$meta"$'\n'"$added")"
        [[ -z "$out" ]] || report "$(git log -1 --no-color --format='%h %s' "$c")" "$out"
    done
done

if ((hits)); then
    echo "ERROR: outgoing commits match the leak-bar term file (above). Push blocked." >&2
    exit 1
fi
echo "leakbar: ok" >&2
