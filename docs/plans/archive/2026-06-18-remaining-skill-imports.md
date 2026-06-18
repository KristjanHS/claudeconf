# Plan: remaining dotfiles skill imports

Status: **closed (complete)** · Created 2026-06-18 · Closed 2026-06-18 — all 11 skills imported (catalog 15 → 26)

Catalog now ships 15 skills (was 5). This plan tracks the **11 dotfiles skills
not yet imported**. Source: `~/projects/dotfiles/claude/.claude/skills/`.

## Decision gate (read first)

These 11 are all general-purpose dev/quality/improvement skills - **none** keep a
session's context lean, which is the catalog's stated thesis. Importing them
pulls the catalog further from its identity (already stretched by Group 1 +
`mybrain`). Decide per group whether the exemplar value is worth the drift
before importing. Under-importing is the cheap, reversible error; bulk-importing
the Kaizen suite is the heaviest identity cost.

## Group 2 - code quality & dev workflow (4)

| Skill | What it does | Import weight |
|---|---|---|
| `testing-anti-patterns` | Catch mock-testing / production pollution in tests | self-contained |
| `finishing-a-development-branch` | Close out a branch: verify tests, hand back | self-contained |
| `python-simplifier` | Simplify/refactor complex Python | `references` + `scripts` subdirs |
| `systematic-debugging` | Structured debugging before proposing fixes | **heavy**: ~10 extra files; ext-ref `anti-patterns-common-rationalizations.md` already in `.claude/references/` |

## Group 3 - Kaizen improvement suite (7, all self-contained, all-or-nothing)

`kaizen-analyse` (pick a method), `kaizen-analyse-problem` (A3 one-pager),
`kaizen-cause-and-effect` (fishbone), `kaizen-kaizen` (iterative improvement /
YAGNI), `kaizen-plan-do-check-act` (PDCA), `kaizen-root-cause-tracing` (trace
bug to trigger), `kaizen-why` (Five Whys). Coherent family - adding one invites
the set. Largest single commitment and the furthest from the catalog identity.

## Import procedure (per skill or batch)

1. `cp -r <dotfiles-skills>/<skill> .claude/skills/`
2. Verify no missing deps: `grep -rhoE '~/\.claude/references/[a-z0-9./-]+\.md' .claude/skills/<skill>`
   - Any hit not already in `.claude/references/` must be copied too (and given a
     pointer line in `.claude/CLAUDE.md` "References").
3. Doc updates (the catalog tracks exact counts - keep them honest):
   - `README.md` catalog row `Skills (×N)` - bump N and add the skill name(s) to
     the right group in the "How it works" cell.
   - `README.md` "The skills (detail)" - bump the "Fifteen `/<name>` skills" count
     word and add a grouped bullet. Add a new `**Group**` heading if the lane is new.
   - If a reference was added: bump `L3 references (×N)` row, the
     progressive-disclosure stat ("N L3 references (~XX KB) ... N references + 4
     rules ... N deferred-load pointer lines"), and add the CLAUDE.md pointer.
   - `ADOPT.md` "5. Skills" - extend the prose; note any non-optional reference dep.
4. Sweep stale counts: `grep -rn "(×<old>)\|<oldword> \`/" --include="*.md" . | grep -v docs/plans/archive/`
5. Confirm `ls .claude/skills/ | wc -l` matches the README count.
6. Commit (gitleaks pre-commit hook runs automatically).

## On close

When this plan is done (or abandoned), `git mv` it to `docs/plans/archive/` and
add it to `.claudeignore`.
