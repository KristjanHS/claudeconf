# Catalog

Everything in this repo, grouped by what it does. For counts and token thresholds see the README's
[measured table](../README.md#whats-measured); to copy a piece, see [ADOPT.md](../ADOPT.md).

## Rules

A rule loads only when Claude reads or edits a file matching its `paths:` patterns. `.claude/CLAUDE.md`
loads every turn, so it holds pointers and a Rules Index instead of the rules themselves.

| Piece | What it does |
|---|---|
| `.claude/CLAUDE.md` | Points at rules and references instead of inlining them. The Rules Index names each rule, so Claude knows it exists before its pattern fires |
| `claude-md-edits.md` | Holds `CLAUDE.md` edits until the session ends. Each line added to `CLAUDE.md` or `MEMORY.md` pushes one out |
| `external-sources.md` | Read and grep vendored copies, submodules and downloaded trees, but run them only through a reviewed entry point |
| `github-actions.md` | Points at `github-actions-local-act.md` |
| `hooks.md` | Hook-authoring traps (PreCompact, SessionStart, PostToolUse I/O); detail in `hooks-deep-dives.md` |
| `instruction-file-discipline.md` | What may go into `CLAUDE.md`, rules, references and `SKILL.md`, so they don't need condensing later |
| `prose-budget.md` | Caps unasked prose (docs, docblocks, comments) at two lines per unit |
| `python-refactors.md` | Import and module-structure refactor traps; detail in `python-refactors-deep-dives.md` |
| `reading-large-files.md` | Forces offset/limit or Grep on lock, csv and minified files |
| `testing.md` | When a test earns its place, test-to-code ratio, pytest defaults |

## References

A reference loads only when a pointer in `CLAUDE.md`, a rule or a skill sends Claude to it.

| Piece | What it does |
|---|---|
| `2026-04-11-context-optimization-research.md` | Startup token table and compaction behaviour, from a 30-source review |
| `anti-patterns-common-rationalizations.md` | Excuses for skipping debugging or design discipline, each with its answer; read by `systematic-debugging` and `testing-anti-patterns` |
| `architecture-assessment-gate.md` | Checklist for the refactor-before-feature call, once planning decides one is warranted |
| `claude-code-persistence.md` | Where Claude Code keeps transcripts, subagent logs and memory under `~/.claude/projects/`, for hook and forensic scripts |
| `dataviz-gotchas.md` | Chart traps the `dataviz` skill's body doesn't spell out |
| `edit-and-plan-gotchas.md` | Why an Edit or Write fails (unread file, stale anchor, duplicate match) and how to fix each |
| `git-commit-gotchas.md` | Pathspec commits on a mixed index and other commit traps |
| `github-actions-local-act.md` | Runs GitHub Actions jobs locally with `act`, no Docker-in-Docker |
| `hooks-deep-dives.md` | The stdin/stdout contract of each hook event, for when `hooks.md` isn't enough |
| `ideation-techniques-library.md` | Ideation techniques for `mybrain`'s deep mode |
| `impag-deep-dives.md` | Rationale and abnormal-path procedures behind each `impag` step |
| `instruction-file-discipline-deep-dives.md` | The moves `instruction-file-discipline.md` allows when condensing an instruction file |
| `iterative-spec-loop.md` | Builds the next increment of a living spec without re-running the full design chain |
| `memory-system.md` | What each memory layer is, who adds to and prunes it, and where retro writes go |
| `mybrain-deep-dives.md` | Why each `mybrain` design-dialogue step exists |
| `pre-ship-sweeps.md` | Sweeps to run before shipping a deny rule, a removal or a threshold change |
| `python-refactors-deep-dives.md` | How each `python-refactors.md` trap bites, with a worked example |
| `reading-large-files-outline-first.md` | Outline a 300–800-line file first, then read only the windows you need |
| `recording-principles.md` | Where an asked-for note goes: `CLAUDE.md`, a rule, a reference or memory |
| `skills-management.md` | Backing up, installing and removing skills without loading the backups |
| `spec-rework-audit.md` | Checks whether a spec review caused re-work |
| `subagent-dispatch.md` | When delegating to a subagent pays, and how to brief one |
| `testing-deep-dives.md` | The falsifying-regime test forms and suite machinery behind `testing.md` |

## Hooks

Hooks run on Claude Code events and cost nothing in context unless they print. Wiring and specs:
[the hooks README](../.claude/hooks/README.md).

| Piece | What it does |
|---|---|
| `settings.json` | Wires each hook to its event and matcher. Merge it into yours by hand |
| `pre-compact.py` | Before compaction (Claude Code summarizing a full window), copies the transcript to a snapshot dir, with the active plan, task and todos in `sidecar.json` |
| `post-compact-restore.py` | After compaction or resume, prints where the newest snapshot is |
| `destructive-bash-gate.py` | Blocks recursive `rm` on roots, download-piped-to-shell and writes into `.ssh`. Writes into ask-guarded paths get a prompt instead |
| `lib/ask_paths.py` | Lets `destructive-bash-gate.py` match paths against the `settings.json` ask globs. Without it, that one check is skipped |
| `docs-bloat-gate.py` | Warns when an `.md` write adds slop phrases, thin text or a new audit doc. Blocks growth past a size cap on `docs/spec.md` and rule files, and any Bash write to them |
| `impag-budget-check.py` | Nudges an `impag` run at 120k, 150k and 175k tokens of context and stops it at 200k, reading the count from the transcript |
| `external-process-test-gate.py` | Keeps docker, browser and HTTP tests in `tests/manual/`, out of the default suite |
| `ruff-check.sh` | Needs `ruff`. After a Python edit lands, tells Claude to fix lint that pushes counts above the committed baseline |
| `pyright-check.sh` | Needs `pyright`. After a Python edit, feeds type errors back to Claude, using the config and venv nearest the file |
| `fetch-quarantine-gate.py` | Blocks cloning or downloading foreign code into a trusted tree; it goes to `~/quarantine/` via `repo-fetch` instead |
| `upstream-exec-gate.py` | Blocks running code from a `vendor/`, `third_party/`, `upstream/` or `quarantine/` dir outside the project's reviewed sandbox |
| `session-start-health.py` | At startup, warns about a `MEMORY.md` near the truncation limit or a `project_state.md` section that doesn't belong |
| `statusline.sh` | Status line: model, context use, a warning near the session stop, 5-hour and 7-day limits |

## Quarantine helpers

Shell tools in `bin/bin/` for vetting a foreign repo before any of it runs; `ext-repo-safety` walks through them.

| Piece | What it does |
|---|---|
| `repo-fetch` | Fetches one pinned commit into `~/quarantine/<name>/src`, hooks off, depth 1 |
| `repo-inspect` | Lists the tree's auto-exec surface (hooks, launch-time configs) without running anything |
| `repo-adopt` | Copies a reviewed pin into your own repo, reading git objects as data; needs `repo-inspect` beside it |
| `vendor-guard` | Refuses vendored code that drifted from its review; runs as a pre-commit check |

## Review loop

| Piece | What it does |
|---|---|
| `agents/code-reviewer.md` | Reviews each finished change in a fresh context, pinned `opus`/`high`, given the plan and commit range but not the author's reasoning |
| `agents/*.md` (7 built-in pins) | Pins each built-in subagent's model and effort, e.g. `Explore` → `haiku`/`low`, `Plan` → `opus`/`high` |
| `agent-model-pin-gate.py` | Blocks an Agent call whose `model` family differs from the agent's pin |

## Skills

A skill's body loads only when you invoke it. The first group keeps context small; the rest are general
tools I keep around.

### Context hygiene

- `condense` deduplicates `CLAUDE.md`, rules and project docs (spec, plans, runbooks) across the
  hierarchy. Run it when the same guidance has drifted into several files, or to move long `CLAUDE.md`
  content into rules and references that load on demand, the method this repo's `CLAUDE.md` was shaped with.
- `de-bloat` (only via `/de-bloat`) audits skill files in `~/.claude/skills/` and a project's
  `.claude/skills/` for bloat and duplication. It edits nothing. It writes a plan for `impag` in two
  passes: content (dedupe, compact), then root cause (which rules, references or skills caused it).
- `impag` executes a plan with parallel subagents, start to finish, without stopping to ask. It takes
  a plan path and defaults to the newest file in `docs/plans/`. The other skills hand their plans to it.
- `qimpag` (only via `/qimpag`) runs `impag` unchanged, but asks one round of questions once it knows
  which plan or stage it's about to build.

### Config and skill management

- `config-reuse` copies Claude configs, rules and settings from another project and detects its stack.
- `install-skill` installs a skill from a GitHub URL or repo path into `~/.claude/skills/`.
- `skills-discovery` looks for an existing skill that handles the current task better than the base model.

### Session hygiene

- `reflect` reviews the session and proposes skill improvements. It runs only on `/reflect` or from a retro.
- `retro` is the end-of-session retrospective: what was learned, and which memories and docs to update.
- `snapshot` (only via `/snapshot`) copies the session transcript into the project's snapshot dir, with
  the active plan and todos in a sidecar, kept apart from the automatic pre-compact snapshots.

### Design and critique

- `senior-architect`: ADRs, tech-stack evaluation, design review, dependency analysis, diagrams.
- `brutal-honesty-review`: blunt critique of code, tests or claims.
- `deep-research`: multi-source web research for questions that need more than one search.
- `architecture-diagram-creator`: HTML architecture diagrams (data flow, components, deployment).
- `mybrain` turns a rough idea into a design by questioning it.

### Code quality and dev workflow

- `testing-anti-patterns` catches tests that only test their mocks, test-only methods leaking into
  production code, and mocks set up without understanding the dependency. Use it when writing tests.
- `systematic-debugging` makes Claude investigate before proposing a fix, for any bug, failing test or
  odd behaviour.
- `python-simplifier` simplifies complex Python: smells, duplication, coupling. Not for Django.
- `ext-repo-safety` vets an external repo before you adopt it: fetch into quarantine, inspect, then adopt.
- `finishing-a-development-branch` verifies tests, reports branch state, merges into `main` and leaves
  `main` checked out. It never pushes.

### Kaizen

Continuous-improvement skills, meant to be copied as a set.

- `kaizen-kaizen` applies Kaizen (small iterations, error-proofing, YAGNI) to one change.
- `kaizen-analyse` picks a method (Gemba, Value Stream or Muda) for a target.
- `kaizen-analyse-problem`: A3 one-page problem analysis, root cause plus actions; carries the 6M fishbone.
- `kaizen-plan-do-check-act`: PDCA experiment cycle.
- `kaizen-why`: Five Whys, from symptom to cause.

### Writing

- `detect-ai-text-humanize` either checks whether text reads as AI-written, with reasons per passage,
  or rewrites it to read as human without showing any detection output.
