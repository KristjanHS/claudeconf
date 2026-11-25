#!/usr/bin/env bash
# Mean wall-clock ms per Bash-wired hook: prints `<hook> <mean ms>`, one line per hook.
# Hooks come from .claude/settings.json (matcher contains Bash); each gets RUNS runs of one sample payload.

set -Eeuo pipefail

ROOT=$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)
RUNS=${RUNS:-5}
PAYLOAD=$(printf '{"session_id":"time-hooks","transcript_path":"/nonexistent","cwd":"%s","tool_name":"Bash","tool_input":{"command":"ls"},"tool_response":{"stdout":"","stderr":"","interrupted":false}}' "$ROOT")

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

for entry in "${HOOKS[@]}"; do
	read -r -a argv <<<"$entry"
	path="$ROOT/.claude/hooks/${argv[0]}"
	[[ -x "$path" ]] || { echo "time-hooks: not executable: $path" >&2; exit 1; }
	total=0
	for _ in $(seq "$RUNS"); do
		t0=$(date +%s%N)
		"$path" "${argv[@]:1}" <<<"$PAYLOAD" >/dev/null 2>&1 || { echo "time-hooks: ${argv[0]} exited $?" >&2; exit 1; }
		total=$((total + $(date +%s%N) - t0))
	done
	echo "${argv[0]} $((total / RUNS / 1000000))"
done
