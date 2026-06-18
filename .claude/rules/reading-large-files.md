---
name: Reading large files
description: Force offset/limit or Grep on file types/sizes where a full read blows the session budget. Unconditional for lock/csv/min; conditional ≥800-line threshold for py/md.
paths:
  - "**/*.lock"
  - "**/*.csv"
  - "**/*.min.js"
  - "**/*.min.css"
  - "**/*.py"
  - "**/*.md"
---

# Reading Large Files

Read tool defaults: 2,000 lines / 2,000 chars/line / 25,000-token hard ceiling. Read also adds ~70% overhead via line-number formatting, so a 1K-line file costs ~8K tokens, a 1.5K-line file ~12K.

## Unconditional — always use offset/limit or Grep

- `*.lock` (package-lock.json, pnpm-lock.yaml, uv.lock, Cargo.lock, Gemfile.lock) — typically 3K–50K lines. Full reads cost ~10% of a 200K context window in one call.
- `*.csv` — unbounded; opening a "small sample" can pull 100K+ rows into context.
- `*.min.js` / `*.min.css` — one line, often multi-megabyte. Truncation hides structure rather than helping.

## Conditional — apply the 800-line threshold

- `*.py` / `*.md` — full Read acceptable under 800 lines. At or above, treat as large:
  - **Under 300 lines**: full Read is fine.
  - **300–800 lines**: prefer Grep for specific symbols; full Read if whole-file structure matters.
  - **≥800 lines**: use `offset`/`limit` or Grep. Full Read needs a stated reason.

Check line count with `wc -l` if unsure — quick and free.

## Rule

**Don't full-Read these without a stated reason. Grep first for known symbols.**

- **Looking for a specific entry/function** → `Grep` with the exact key/pattern.
- **Need a structural sample (small file, single entry point)** → `Read` with `offset: 0, limit: 80`.
- **Targeted range** → once Grep tells you a symbol is at line N, `Read(offset=N-10, limit=60)`.
- **Comparing two lock files** → `Bash` with `diff <(jq -S . a.lock) <(jq -S . b.lock)` or similar — let the tool emit only the delta.
- **Must scan end-of-file** → `Read` with explicit `offset` at the tail, not a full read.
- **Multi-section structural understanding** → outline-first tree: `~/.claude/references/reading-large-files-outline-first.md`.

**Declare intent before reading.** One sentence — "reading X to find Y" — before Read/Grep on a large file. The declaration forces the Grep-vs-Read decision before spending tokens.
