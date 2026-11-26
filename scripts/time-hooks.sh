#!/usr/bin/env bash
# Mean wall-clock ms per Bash-wired hook: prints `<hook> <mean ms>`, one line per hook.
# Hooks come from .claude/settings.json (matcher contains Bash); each gets RUNS runs of one sample payload.
# Needs bash >= 4 (mapfile) and GNU date (%N nanoseconds).

set -Eeuo pipefail

ROOT=$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)
RUNS=${RUNS:-5}
[[ $RUNS =~ ^[1-9][0-9]*$ ]] || { echo "time-hooks: RUNS must be a positive integer, got '$RUNS'" >&2; exit 1; }

# A transcript above impag-budget-check's FALLBACK_PROBE_BYTES floor (400 KB), ending in an
# assistant usage line, so that hook times its tail read instead of its early return.
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
TRANSCRIPT="$TMP/time-hooks.jsonl"
python3 - "$TRANSCRIPT" <<'PY'
import json, sys
filler = json.dumps({"type": "user", "message": {"role": "user", "content": "x" * 1000}})
with open(sys.argv[1], "w") as f:
    for _ in range(450):
        f.write(filler + "\n")
    f.write(json.dumps({"type": "assistant", "message": {"role": "assistant", "usage": {
        "input_tokens": 10, "cache_creation_input_tokens": 1000, "cache_read_input_tokens": 99000}}}) + "\n")
PY

PAYLOAD=$(printf '{"session_id":"time-hooks","transcript_path":"%s","cwd":"%s","tool_name":"Bash","tool_input":{"command":"ls"},"tool_response":{"stdout":"","stderr":"","interrupted":false}}' "$TRANSCRIPT" "$ROOT")

# Settings wire `~/.claude/hooks/<file> [args]`; time this repo's copy of each.
mapfile -t HOOKS < <(python3 - "$ROOT/.claude/settings.json" <<'PY'
import json, sys
for matchers in json.load(open(sys.argv[1])).get("hooks", {}).values():
    for m in matchers:
        if "Bash" in m.get("matcher", "").split("|"):
            for h in m.get("hooks", []):
                print(h["command"].split("/.claude/hooks/", 1)[-1])
PY
)

[[ ${#HOOKS[@]} -gt 0 ]] || { echo "time-hooks: no Bash hooks in settings.json" >&2; exit 1; }

# Python hooks wrap main() in `except Exception: sys.exit(0)`, so a crash would time as a fast
# success. One untimed run per .py hook calls main() directly; an exception or non-zero exit fails.
CHECK_PY='
import runpy, sys
sys.argv = sys.argv[1:]
try:
    rc = runpy.run_path(sys.argv[0], run_name="th")["main"]()
except SystemExit as e:
    rc = e.code
sys.exit(0 if rc in (None, 0) else 1)
'
check_py() { python3 -c "$CHECK_PY" "$@" <<<"$PAYLOAD" >/dev/null; }

for entry in "${HOOKS[@]}"; do
	read -r -a argv <<<"$entry"
	path="$ROOT/.claude/hooks/${argv[0]}"
	[[ -x "$path" ]] || { echo "time-hooks: not executable: $path" >&2; exit 1; }
	if [[ $path == *.py ]]; then
		check_py "$path" "${argv[@]:1}" || { echo "time-hooks: ${argv[0]} main() failed its check run" >&2; exit 1; }
	fi
	total=0
	for _ in $(seq "$RUNS"); do
		t0=$(date +%s%N)
		"$path" "${argv[@]:1}" <<<"$PAYLOAD" >/dev/null 2>&1 || { echo "time-hooks: ${argv[0]} exited $?" >&2; exit 1; }
		total=$((total + $(date +%s%N) - t0))
	done
	echo "${argv[0]} $((total / RUNS / 1000000))"
done
