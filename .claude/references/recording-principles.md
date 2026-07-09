# Information Recording Principles

## Before recording (write-time discipline - runs every time)

Each of these fires *before* picking a target file. Skipping any of them is how the rule files bloated in the first place - see `~/.claude/rules/instruction-file-discipline.md` for the full rationale.

1. **Grep the candidate target first.** If a similar bullet already exists, propose an `Edit` to that bullet - never append a near-duplicate. If 2+ similar bullets exist, this is a `condense` trigger; merge inline with the new content rather than adding a third.
2. **Stranger test → routes global vs project.** Ask: "would this make sense to a stranger with no knowledge of project X?" If the answer mentions a date, a `file.py:line`, or a project-only path → file under that project's `.claude/rules/`, not `~/.claude/rules/` or global CLAUDE.md.
3. **Default OFF for "Why this rule exists" prose.** Add it only when a future reader couldn't reconstruct the reason from the rule text. Incident dates, commit SHAs, file:line refs belong in the **commit message**, not the rule body.
4. **Size budget self-check.** Before appending, eyeball the target: `~/.claude/CLAUDE.md` Interaction Style ≤10 bullets; `.claude/rules/*.md` ≤80 lines; `SKILL.md` ≤100 lines. At/over budget → condense first, then append.

If any of these is unclear in context, stop and ask the user - silent skipping is the bloat path.

## What belongs in L1 (CLAUDE.md content types)

| Type | Example |
|------|---------|
| Iron rules / prohibitions | Never commit secrets; never hardcode calculated values |
| Core commands | `python -m yourpkg build` |
| Workflow constraints | Absolute paths for all tool calls |
| Error diagnostics | Symptom → cause → fix |
| Code patterns | Copy-paste ready snippets |
| Directory map | Function → file |
| Trigger indexes | Pointers to L2 docs |

## Routing tree (project × global, by tier)

| Tier | Project location | Global location | Loaded |
|------|------------------|-----------------|--------|
| L1 | `./CLAUDE.md` | `~/.claude/CLAUDE.md` | Always |
| Skills | `~/.claude/skills/<name>/SKILL.md` (project-local skills are rare; most projects don't define their own) | `~/.claude/skills/<name>/SKILL.md` | Description always indexed; body on description match |
| L2 path-gated | `./.claude/rules/*.md` (`paths` frontmatter) | `~/.claude/rules/*.md` (`paths` frontmatter) | When matching files read/edited |
| L3 manual | `./docs/*.md` | `~/.claude/references/*.md` | When an L1/L2 pointer fires |

Note: project incident *archives* (postmortems, "which incident drove this rule" audits) belong at L3 (`./docs/`), not L2 - see `~/.claude/rules/instruction-file-discipline.md` § Tier discipline.

Skills: use for ≥3-step workflows tied to a user trigger that a CLAUDE.md bullet can't capture.

## When asked to record information

1. High-frequency or iron-rule? → CLAUDE.md (L1) at matching scope
2. Multi-step workflow tied to a user trigger? → SKILL.md at matching scope
3. Domain-specific workflow tied to file types? → `~/.claude/rules/` with `paths` frontmatter (global only)
4. Detailed SOP / edge case / reference? → `./docs/*.md` (project) or `~/.claude/references/*.md` (global) - every entry needs a **trigger condition** (when to read it)
