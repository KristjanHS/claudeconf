#!/usr/bin/env bash
# verify-target.sh <repo> [--stages "target commit push"] [--targets "LIST"] [--keep] — gate matrix on a fresh clone; TSV on stdout, exit 1 on any FAIL.
set -uo pipefail

repo="" stages="target commit push" targets="help sync check fmt audit test" keep=0
while [ $# -gt 0 ]; do
    case "$1" in
        --stages) stages="$2"; shift 2 ;;
        --targets) targets="$2"; shift 2 ;;
        --keep) keep=1; shift ;;
        -*) echo "verify-target: unknown flag $1" >&2; exit 2 ;;
        *) repo="$1"; shift ;;
    esac
done
usage() { echo "usage: verify-target.sh <repo> [--stages 'target commit push'] [--targets LIST] [--keep]" >&2; exit 2; }
[ -n "$repo" ] || usage
[ -n "${stages// /}" ] || usage
for s in $stages; do
    case "$s" in target | commit | push) ;; *) echo "verify-target: unknown stage $s" >&2; usage ;; esac
done

# Never under /tmp: a target sandboxing with a tmpfs over /tmp (bwrap) would hide its own clone.
cache="${XDG_CACHE_HOME:-$HOME/.cache}"
mkdir -p "$cache" && scratch="$(mktemp -d "$cache/verify-target.XXXXXX")" || exit 2
fail=0
trap 'if [ "$keep" = 1 ] || [ "$fail" != 0 ]; then echo "verify-target: kept $scratch (rm -rf when done)" >&2; else rm -rf "$scratch"; fi' EXIT
clone="$scratch/clone"
git clone -q --recurse-submodules "$repo" "$clone" || exit 2
git init -q --bare "$scratch/verify.git"
git -C "$clone" remote add verify "$scratch/verify.git"
git -C "$clone" config shellcheckhook.force true # the global shellcheck hook skips repos under /tmp
make -C "$clone" -pRrq : >"$scratch/make-db.txt" 2>/dev/null

row() { # STAGE CASE EXPECT GOT
    local verdict=PASS
    [ "$4" = skip ] && verdict=SKIP
    [ "$3" != "$4" ] && [ "$4" != skip ] && { verdict=FAIL; fail=1; }
    printf '%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$verdict"
}
has_target() { # <t> — a real rule in the make db; not a .PHONY-only name, a variable, or a file/dir
    awk -v t="$1" '
        /^# Files/ { f = 1; next }
        /^# files hash/ { f = 0 }
        !f { next }
        /^# Not a target:/ { nt = 1; next }
        /^$/ { if (in_t) exit; nt = 0; next }
        !in_t && !nt && index($0, t ":") == 1 {
            rest = substr($0, length(t) + 2); sub(/^:/, "", rest)
            if (rest ~ /=/) next
            in_t = 1; if (rest ~ /[^ \t]/) ok = 1; next
        }
        in_t && /^#  recipe to execute/ { ok = 1 }
        END { exit !ok }' "$scratch/make-db.txt"
}
reset_clone() { git -C "$clone" reset -q --hard && git -C "$clone" clean -fdq; }

on() { [[ " $stages " == *" $1 "* ]]; }

printf 'STAGE\tCASE\tEXPECT\tGOT\tVERDICT\n'
on target || targets=""
for t in $targets; do
    if ! has_target "$t"; then
        if [ "$t" = check ]; then row target "$t" pass absent; else row target "$t" pass skip; fi # check is mandatory
        continue
    fi
    if ! make -C "$clone" --no-print-directory "$t" >"$scratch/target-$t.log" 2>&1; then
        got=nonzero
    elif [ -n "$(git -C "$clone" status --porcelain)" ]; then
        got=dirty
    else
        got=pass
    fi
    row target "$t" pass "$got"
    reset_clone
done

on commit || on push || exit "$fail"
export GIT_AUTHOR_DATE=2026-01-03T12:00:00+02:00 GIT_COMMITTER_DATE=2026-01-03T12:00:00+02:00 # Saturday: date-gated push hooks pass
base="$(git -C "$clone" rev-parse HEAD)" branch="$(git -C "$clone" symbolic-ref --short HEAD)"
if has_target sync && ! make -C "$clone" --no-print-directory sync >"$scratch/sync.log" 2>&1; then
    keep=1; echo "verify-target: make sync failed ($scratch/sync.log)" >&2
fi
if [ -f "$clone/.pre-commit-config.yaml" ]; then
    pc=pre-commit
    [ -x "$clone/.venv/bin/pre-commit" ] && pc="$clone/.venv/bin/pre-commit"
    if ! (cd "$clone" && "$pc" install --hook-type pre-commit --hook-type pre-push) >"$scratch/hooks.log" 2>&1; then
        keep=1; echo "verify-target: pre-commit install failed ($scratch/hooks.log)" >&2
    fi
fi

# Commit stage: plant one defect per probe; GOT is read from HEAD, never from hook logs.
plant() { # <case> — writes the probe file(s) into the clone
    case "$1" in
        big.bin) head -c 307200 /dev/urandom >"$clone/big.bin" ;;
        probe.pdf) printf x >"$clone/probe.pdf" ;;
        f401.py) printf 'import os\n' >"$clone/f401.py" ;;
        fmt.py) printf 'x=1\n' >"$clone/fmt.py" ;;
        bad.sh) printf '#!/bin/bash\nif true; then\n' >"$clone/bad.sh" ;;
        bad.yaml) printf 'a: [\n' >"$clone/bad.yaml" ;;
        secret.txt) printf 'ghp_%s\n' "$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 36)" >"$clone/secret.txt" ;;
        ok.txt) printf 'ok\n' >"$clone/ok.txt" ;;
    esac
}
on commit && for c in big.bin probe.pdf f401.py fmt.py bad.sh bad.yaml secret.txt ok.txt; do
    git -C "$clone" reset -q --hard "$base" && git -C "$clone" clean -fdq
    plant "$c"
    git -C "$clone" add -A && git -C "$clone" commit -qm "probe $c" >"$scratch/commit-$c.log" 2>&1
    if [ "$(git -C "$clone" rev-parse HEAD)" = "$base" ]; then got=refused; else got=accepted; fi
    expect=refused
    [ "$c" = ok.txt ] && expect=accepted
    row commit "$c" "$expect" "$got"
    [ "$c" = ok.txt ] && [ "$got" = refused ] && echo "verify-target: control refused — blanket refusal, refused rows prove nothing" >&2
done

# Push stage: each case pushes a fresh commit; GOT is read from the remote ref, never from hook logs.
pushcase() { # <case> — leaves the clone ready to push; echoes the ref to push
    local c="$1"
    git -C "$clone" checkout -q "$branch" && git -C "$clone" reset -q --hard "$base" && git -C "$clone" clean -fdq
    git -C "$clone" branch -q -D other 2>/dev/null
    case "$c" in
        other) git -C "$clone" checkout -q -b other ;;
        ws.txt) printf 'a \n' >"$clone/ws.txt" ;;
    esac
    printf '%s\n' "$c" >"$clone/push-$c.txt"
    git -C "$clone" add -A && git -C "$clone" commit -q --no-verify -m "push probe $c"
    case "$c" in
        other) git -C "$clone" checkout -q "$branch"; echo other ;;
        dirty.txt) printf 'x\n' >"$clone/dirty.txt"; echo "$branch" ;;
        *) echo "$branch" ;;
    esac
}
if on push; then
    for c in dirty.txt ws.txt other ok-push; do
        # Reset the remote too: a ref an earlier case got accepted would make this push a non-fast-forward.
        git -C "$clone" push -qf --no-verify verify "$base:refs/heads/$branch" 2>/dev/null
        ref="$(pushcase "$c")"
        before="$(git -C "$clone" ls-remote verify "refs/heads/$ref")"
        git -C "$clone" push -q verify "$ref" >"$scratch/push-$c.log" 2>&1
        if [ "$(git -C "$clone" ls-remote verify "refs/heads/$ref")" = "$before" ]; then got=refused; else got=accepted; fi
        expect=refused
        [ "$c" = ok-push ] && expect=accepted
        row push "$c" "$expect" "$got"
        [ "$c" = ok-push ] && [ "$got" = refused ] && echo "verify-target: push control refused ($scratch/push-$c.log)" >&2
    done
    git -C "$clone" checkout -q "$branch"
fi
git -C "$clone" reset -q --hard "$base" && git -C "$clone" clean -fdq
exit "$fail"
