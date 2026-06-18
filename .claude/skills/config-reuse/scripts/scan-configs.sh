#!/usr/bin/env bash
# scan-configs.sh — Inventory Claude configs in a source project with language/domain markers
# Usage: scan-configs.sh <SOURCE_PROJECT_PATH>
# Output: TSV — TYPE  REL_PATH  MD5  MARKERS

set -euo pipefail

SOURCE="${1:-}"
[[ -z "$SOURCE" ]] && { echo "Usage: scan-configs.sh /path/to/project" >&2; exit 1; }
SOURCE="$(realpath "$SOURCE")"
[[ -d "$SOURCE" ]] || { echo "ERROR: Not a directory: $SOURCE" >&2; exit 1; }

printf 'TYPE\tREL_PATH\tMD5\tMARKERS\n'

detect_markers() {
  local f="$1" m=""
  # Language — require word boundaries via \b or unambiguous tool names
  grep -qwi 'pytest\|pyright\|pyproject\|\.py\b\|ruff\|pip install\|python3\?\b' "$f" 2>/dev/null && m="${m}python,"
  grep -qwi 'typescript\|tsconfig\|\.tsx\?\b\|tsc\b' "$f" 2>/dev/null && m="${m}typescript,"
  grep -qwi 'npm\|node\b\|\.jsx\?\b\|package\.json\|yarn\|bun\b' "$f" 2>/dev/null && m="${m}javascript,"
  grep -qwi 'cargo\|\.rs\b\|rustc\|crate' "$f" 2>/dev/null && m="${m}rust,"
  grep -qwi 'go\.mod\|go\.sum\|golang\|go test' "$f" 2>/dev/null && m="${m}go,"
  # Tools
  grep -qwi 'pytest\|jest\|vitest\|playwright\|cypress' "$f" 2>/dev/null && m="${m}testing,"
  grep -qwi 'ruff\|eslint\|prettier\|black\|flake8' "$f" 2>/dev/null && m="${m}linter,"
  grep -qwi 'docker\|dockerfile\|compose' "$f" 2>/dev/null && m="${m}docker,"
  # Domain — use multi-word phrases or unambiguous terms to avoid false positives
  grep -qiE 'project.manag|work.package|gantt chart|resource.alloc|mileston.+deliver' "$f" 2>/dev/null && m="${m}DOMAIN:pm,"
  grep -qiE 'patient record|clinical trial|medical diagno|HIPAA' "$f" 2>/dev/null && m="${m}DOMAIN:medical,"
  grep -qiE 'stock market|portfolio.+asset|financial.+report|banking.+API' "$f" 2>/dev/null && m="${m}DOMAIN:finance,"
  grep -qiE 'NATO\b|SITREP\b|locked.shields|military.+exercise' "$f" 2>/dev/null && m="${m}DOMAIN:military,"
  echo "${m%,}"
}

emit() {
  local type="$1" file="$2" rel="$3"
  local md5 markers
  md5=$(md5sum "$file" 2>/dev/null | cut -d' ' -f1)
  markers=$(detect_markers "$file")
  printf '%s\t%s\t%s\t%s\n' "$type" "$rel" "$md5" "${markers:-none}"
}

# Root CLAUDE.md variants
for f in CLAUDE.md CLAUDE.local.md; do
  [[ -f "$SOURCE/$f" ]] && emit claude_md "$SOURCE/$f" "$f"
done
[[ -f "$SOURCE/.claude/CLAUDE.md" ]] && emit claude_md "$SOURCE/.claude/CLAUDE.md" ".claude/CLAUDE.md"

# .claudeignore
[[ -f "$SOURCE/.claudeignore" ]] && emit claudeignore "$SOURCE/.claudeignore" ".claudeignore"

# Rules
if [[ -d "$SOURCE/.claude/rules" ]]; then
  for f in "$SOURCE/.claude/rules/"*.md; do
    [[ -f "$f" ]] || continue
    emit rule "$f" ".claude/rules/$(basename "$f")"
  done
fi

# Commands (recursive)
if [[ -d "$SOURCE/.claude/commands" ]]; then
  while IFS= read -r -d '' f; do
    emit command "$f" "${f#"$SOURCE/"}"
  done < <(find "$SOURCE/.claude/commands" -name "*.md" -type f -print0 | sort -z)
fi

# Skills
if [[ -d "$SOURCE/.claude/skills" ]]; then
  while IFS= read -r -d '' f; do
    emit skill "$f" "${f#"$SOURCE/"}"
  done < <(find "$SOURCE/.claude/skills" -name "SKILL.md" -type f -print0 | sort -z)
fi
