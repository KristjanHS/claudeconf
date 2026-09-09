#!/usr/bin/env bash
#
# docs-report.sh — advisory size report for instruction files.
#
# Ported from ~/projects/dotfiles/scripts/docs-report.sh, re-pathed for this
# repo's flat .claude/ layout. Prints sizes, marks what is over a soft target,
# and RECOMMENDS NOTHING. There is no required remedy — split into a reference,
# condense, or accept, whichever the author judges right.
#
# ALWAYS EXITS 0. Nothing here blocks a commit or a push.
#
# Soft targets are report-only reference points, except the skill-body one:
# ~15 KB ~= Anthropic's documented "keep SKILL.md body under 500 lines"
# (platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices),
# whose own remedy is to split into reference files, not to compress prose.

set -Eeuo pipefail

ROOT=$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)

SOFT_SKILL=15000
SOFT_REFERENCE=24000
SOFT_CLAUDE_MD=24000
SOFT_RULE=8000

over_count=0

# Body = everything after the closing `---` of YAML frontmatter, `wc -c`. For a
# file without frontmatter, the whole file.
_body_bytes() {
    local f=$1 end
    end=$(awk 'NR>1 && /^---[[:space:]]*$/{print NR; exit}' "$f")
    if [ -z "$end" ]; then
        wc -c <"$f"
    else
        tail -n +"$((end + 1))" "$f" | wc -c
    fi
}

_row() {
    local label=$1 bytes=$2 soft=$3 mark=""
    if [ "$bytes" -gt "$soft" ]; then
        mark="  OVER"
        over_count=$((over_count + 1))
    fi
    printf '    %-42s %6d / %6d%s\n' "$label" "$bytes" "$soft" "$mark"
}

echo "docs-report — advisory only, nothing here blocks a commit or push"
echo

echo "  ALWAYS LOADED (re-billed every turn)"
for f in "$ROOT/.claude/CLAUDE.md" "$ROOT/CLAUDE.md"; do
    [ -f "$f" ] || continue
    _row "${f#"$ROOT"/}" "$(wc -c <"$f")" "$SOFT_CLAUDE_MD"
done
echo

echo "  PATH-GATED RULES (reference point only — nothing fails over it)"
while IFS= read -r rel; do
    _row "${rel#.claude/rules/}" "$(wc -c <"$ROOT/$rel")" "$SOFT_RULE"
done < <(git -C "$ROOT" ls-files '.claude/rules/*.md' | sort)
echo

echo "  SKILL BODIES (lazy-loaded — soft target only, no required remedy)"
while IFS= read -r rel; do
    _row "${rel#.claude/skills/}" "$(_body_bytes "$ROOT/$rel")" "$SOFT_SKILL"
done < <(git -C "$ROOT" ls-files '.claude/skills/*/SKILL.md' | sort)
echo

echo "  L3 REFERENCES (loaded on demand — soft target only)"
while IFS= read -r rel; do
    _row "${rel#.claude/references/}" "$(wc -c <"$ROOT/$rel")" "$SOFT_REFERENCE"
done < <(git -C "$ROOT" ls-files '.claude/references/*.md' | sort)
echo

if [ "$over_count" -eq 0 ]; then
    echo "  nothing over target."
else
    echo "  $over_count file(s) over a soft target. No action required —"
    echo "  split into a reference, condense, or accept. Author's judgment."
fi

exit 0
