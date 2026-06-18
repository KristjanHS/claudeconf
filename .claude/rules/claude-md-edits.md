---
name: CLAUDE.md editing cadence
description: Batch CLAUDE.md edits to session boundaries - mid-session edits invalidate the session-specific cache suffix.
paths:
  - "**/CLAUDE.md"
---

# CLAUDE.md Editing Cadence

The system prompt splits at a dynamic boundary: the base prefix (system prompt + tool defs) stays cacheable across turns within the session; the suffix (CLAUDE.md, cwd, git status, date, active skills) is the session-specific tail. Editing CLAUDE.md mid-session invalidates the **session-specific suffix only** - not the larger base prefix - but the rewrite-and-re-read cost is still turn-over-turn material (write ≈ 125% of the suffix, read ≈ 10%).

## Rule

**Batch CLAUDE.md edits to end-of-session or start of next.** Don't amend CLAUDE.md in the middle of a coding task.

Ship-immediately exceptions (small, one-off):
- An Iron Rule update (safety cannot wait).
- A typo or broken reference that misleads the current session.

Bundle these for end-of-session:
- New Efficiency guidance surfaced in a retro.
- Rules Index additions when a new path-gated rule lands.
- Clarifications to Interaction Style.

When bundling, ship as one commit - a chain of three separate CLAUDE.md commits costs three suffix-cache breaks where one would do.
