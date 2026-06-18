# Writing targets — rule body, frontmatter, condense, sweep, archive

Loaded on demand from retro Step 3/4 when there's something to write. Contains the schemas and procedures that would otherwise pad the main skill body.

## Canonical rule body — three lines

Use this shape for new bullets and for any rule body you rewrite in this retro. Don't proactively rewrite existing conformant rules.

- *Rule statement* — imperative, one line
- **Why:** the reason (invariant, incident-class, constraint)
- **How to apply:** trigger condition (when/where it fires)

Incident dates, commit SHAs, and `file.py:123` refs belong in the **commit message**, not the rule body. "Exact text" proposals must conform.

## Rule frontmatter (`.claude/rules/*.md`)

- `last_verified: YYYY-MM-DD` — required; bump when re-confirmed
- `expires_after: 180d` — optional (default 180d)

Avoid in rule bodies: hyperbolic language, vague instructions, historical comments, duplication.

## Size budgets

Condense when at or over — don't just keep appending:

- `~/.claude/CLAUDE.md` Interaction Style: ≤10 bullets
- Each `.claude/rules/*.md`: ≤80 lines
- Each SKILL.md we own: ≤100 lines

## 4b. Condense if over budget

If any file touched in retro Steps 2–4 is now over its size budget, condense before ending the retro:

- CLAUDE.md → invoke `claude-md-progressive-disclosurer`
- Rules / skills → apply inline condense (merge overlap, drop narrative, supersede-and-delete)

Budget-crossing is the mandatory condense trigger.

## 4c. Stale-rule sweep

For each `~/.claude/rules/*.md`, if `last_verified + expires_after < today`, ask the user "still load-bearing?" — bump `last_verified` or delete the rule. Run once per retro; skip if no rule is near expiry.

## Archive closed plans

When `project_state.md` marks a plan COMPLETE and its follow-ups are closed or tracked elsewhere:

1. `git mv` the plan doc into `<project>/docs/plans/archive/`
2. Ensure `docs/plans/archive/` is listed in `.claudeignore` so Claude doesn't auto-load stale plans
3. Trim the plan's narration from `project_state.md` — the archived doc + git history preserve it
