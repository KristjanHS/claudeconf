---
name: CLAUDE.md editing cadence
description: Batch CLAUDE.md edits to session boundaries, and hold the always-resident tier (CLAUDE.md, MEMORY.md) to one-in-one-out.
paths:
  - "**/CLAUDE.md"
  - "**/.claude/CLAUDE.md"
  - "**/MEMORY.md"
---

# CLAUDE.md Editing Cadence

The system prompt splits at `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__`: the base prefix (system prompt + tool defs, ~14,500 tok) stays cacheable across turns within the session; the suffix (CLAUDE.md, cwd, git status, date, active skills) is the session-specific tail. Editing CLAUDE.md mid-session invalidates the **session-specific suffix only** — not the larger base prefix — but at high/xhigh effort the rewrite-and-re-read cost is still turn-over-turn material (write = 125% base, read = 10% base).

## Rule

**Batch CLAUDE.md edits to end-of-session or start of next.** Don't amend CLAUDE.md in the middle of a coding task.

Ship-immediately exceptions (small, one-off):
- An Iron Rule update (safety cannot wait).
- A typo or broken reference that misleads the current session.

Bundle these for end-of-session:
- New Efficiency guidance surfaced in a retro.
- A new path-gated rule needs a CLAUDE.md edit **only if that CLAUDE.md already indexes rules** — grep it
  first. Its `paths:` frontmatter is the whole wiring, so **never add an index to a CLAUDE.md that lacks
  one** (a pointer to a file that loads itself fires at no seam and is billed every turn). Same for a
  `~/.claude/references/` file: list it in CLAUDE.md only when nothing in `~/.claude/rules/`, the CLAUDE.md
  body or `~/.claude/skills/` already points at it — grep the stem across all three before adding a line.
- Clarifications to Interaction Style.

When bundling, ship as one commit — a chain of three separate CLAUDE.md commits costs three suffix-cache breaks where one would do.

## One in, one out — the always-resident tier has no other brake

`~/.claude/CLAUDE.md`, `<project>/CLAUDE.md` and `memory/MEMORY.md` are billed on **every turn of every
session**, so a line added here is rent, not a one-time cost. ⛔ Not a byte cap — those are killed
(`~/.claude/references/memory-system.md` §No size caps). The verb is the symmetric one
a private project's plan-hygiene.md §Claims already applies to ordinals:

**A line added to any of the three graduates a line OUT, in the same edit burst** — to a path-gated
`.claude/rules/` file, a `~/.claude/references/` file, or a project doc. **If nothing can leave, the new
line does not enter**: put it at its seam instead (the code comment, the test, the rule that already fires
on that path) — **as ONE line, never a paragraph** (`~/.claude/rules/prose-budget.md`).

Prefer the gated home *first*. Guidance needed only while editing a particular surface belongs to that
surface's rule, where it costs nothing on the turns that don't touch it — and an existing rule already
gated on that path is a better home than a new file, which would fire alongside it at the same seam.

Evidence for the drift and the arithmetic →
a private project's 2026-08-09-session-token-audit-round-2.md §1 (this rule fires in
every project, so that cite is rooted, not stem-relative — and the doc shipped, so the path is terminal).
