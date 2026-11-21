# Why this exists

The short version is in the [README](../README.md#-why-this-exists); the
layers themselves are on [How the system works](system.md). This page is the
reasoning behind them.

## The problem

A coding agent fails in two ways that compound. A long session gets slow,
expensive and forgetful: the window fills with rule text, stale docs and
re-derived state, and compaction drops the reasoning that lived only in the
conversation ([README: The problem](../README.md#-the-problem)).

The second failure is quieter: the agent's output **looks done**. Code passes the
tests it wrote for itself, a check reports green because it cannot fail, and a
doc states a claim nobody re-checked. An agent never tires of writing, so docs
grow until they crowd out the context the work needs.

## Why this method

Each failure gets a layer ([How the system works](system.md)), and three
choices shape all of them:

- **Copy-in, not auto-install.** Auto-merging into someone's `settings.json` is
  the most likely way to break their config, so every piece is adopted by hand
  ([ADOPT.md](../ADOPT.md)).
- **Written for the doubter.** Each piece states what it costs and where it
  isn't worth it ([What it costs you](../README.md#-what-it-costs-you),
  [When this isn't worth it](../README.md#-when-this-isnt-worth-it)).
- **A check must be able to fail.** A gate or test that passes by construction
  reads as proof forever, so new checks ship with a red demo: break the line it
  guards, watch it fail, restore it.

## What agents got wrong

| What the agent got wrong | Answered by | Proof |
|---|---|---|
| Docs grow faster than anyone re-reads them | [Bloat gate](../.claude/hooks/docs-bloat-gate.py) ([Gates](system.md#gates-flag-or-block-the-output-that-isnt)) | [What it costs you](../README.md#-what-it-costs-you): slop, density and new-doc signals nudge; only the opt-in size ratchet blocks |
| A leak gate that reads its own error as "clean" | [PII check](../scripts/check-hardcoded-paths.sh), beside the [pre-commit](../hooks/pre-commit) secret gate and [gitleaks CI](../.github/workflows/gitleaks.yml) | [`2ad3e5a`](https://github.com/KristjanHS/claudeconf/commit/2ad3e5a): review found a git error printed "no leakage" and exited 0; now it fails closed, red demo in the message |
| Context burns until compaction drops the reasoning | [Budget governor](../.claude/hooks/impag-budget-check.py) ([Cost budget](system.md#cost-budget-stop-a-run-before-it-burns-its-context)) | [Budget governor detail](../README.md#-the-budget-governor-detail) |
| Plausible code that passes the tests it wrote | Review loop in a fresh context ([Review loop](system.md#review-loop-catch-what-slips-past-the-gates)) | [`20a7475`](https://github.com/KristjanHS/my-vector/commit/20a7475): the old month test never crossed a month; review caught a seal a late restart could falsify |

## Worked trails

Each trail runs plan → building commit → the review fix that corrected it.

**[my-vector](https://github.com/KristjanHS/my-vector)**: sealing the first
real-use window.

- Plan: [prod evidence](plans/2026-11-15-my-vector-prod-evidence.md)
- Build: [`da037e6`](https://github.com/KristjanHS/my-vector/commit/da037e6) `make prod-check` (Stage 3)
- Review fix: [`20a7475`](https://github.com/KristjanHS/my-vector/commit/20a7475): a day counts as final only before the last saved poll; the tag pins `origin/main`, never a local-only HEAD

**[transcribe-offline](https://github.com/KristjanHS/transcribe-offline)**:
hardening an offline transcriber.

- Plan: [security critique](https://github.com/KristjanHS/transcribe-offline/blob/main/docs/plans/archive/2026-09-27-security-critique-todo.md)
- Build: [`1137856`](https://github.com/KristjanHS/transcribe-offline/commit/1137856) installer and CI hardening (Stage 3)
- Review fix: [`1deb918`](https://github.com/KristjanHS/transcribe-offline/commit/1deb918): if deleting a mismatched `uv.exe` failed, the download block was skipped and its post-check with it, so an unverified `uv.exe` ran; the check now runs on every path
