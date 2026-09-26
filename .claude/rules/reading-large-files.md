---
name: Reading large files
description: Force offset/limit or Grep on file types/sizes where a full read blows the 300k session-stop budget. Unconditional for lock/csv/min; the ≥800-line conditional for source/prose lives in global CLAUDE.md §Efficiency.
paths:
  - "**/*.lock"
  - "**/*.csv"
  - "**/*.min.js"
  - "**/*.min.css"
---

# Reading Large Files

Read tool defaults: 2,000 lines / 2,000 chars/line / 25,000-token hard ceiling. Read also adds ~70% overhead via line-number formatting, so a 1K-line file costs ~8K tokens, a 1.5K-line file ~12K.

## Unconditional — always use offset/limit or Grep

- `*.lock` (package-lock.json, pnpm-lock.yaml, uv.lock, Cargo.lock, Gemfile.lock) — typically 3K–50K lines. Full reads cost ~7% of the 300K session-stop budget in one call.
- `*.csv` — unbounded; opening a "small sample" can pull 100K+ rows into context.
- `*.min.js` / `*.min.css` — one line, often multi-megabyte. Truncation hides structure rather than helping.

## Conditional — apply the 800-line threshold

- `*.py` / `*.md` / `*.ts` / `*.js` — full Read acceptable under 800 lines. At or above, treat as large:
  - **Under 300 lines**: full Read is fine — but **one pass**. Having confirmed it's small, read the whole file in a single call; never fragment an under-threshold file into 2+ overlapping offset windows (repeated tool overhead, zero new information). Choose the read strategy *from the checked size*, not by defaulting to windows.
  - **300–800 lines**: prefer Grep for specific symbols; full Read if whole-file structure matters.
  - **≥800 lines**: use `offset`/`limit` or Grep. Full Read needs a stated reason.

Check line count with `wc -l` if unsure — quick and free.

## Rule

**Don't full-Read these without a stated reason. Grep first for known symbols; once Grep gives you the line N, `Read(offset=N-10, limit=60)`.** If you intend to Edit the file, the pipeline must end in that Read — Grep alone (tool or Bash `grep`/`sed`) never satisfies Edit's read precondition, no matter how much content it put in context.

**Declare intent before reading.** One sentence — "reading X to find Y" — before Read/Grep on a large file. The declaration forces the Grep-vs-Read decision before spending tokens.

**Per-situation how-to** (structural sample, 300–800-line outline-first tree, lock-file diff, scan-EOF, the banned overlapping-offset shape, silent session-budget warning) → `~/.claude/references/reading-large-files-outline-first.md`. Read it when in doubt, or whenever 2+ overlapping offset Reads on one file are queued up.
