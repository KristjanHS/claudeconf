# Catalog

Everything in this repo, grouped by what it does. For counts and token thresholds see the README's
[measured table](../README.md#whats-measured); to copy a piece, see [ADOPT.md](../ADOPT.md).

### Rules

Loaded only when a matching file is touched.

| Piece | Purpose | How it works | Cost |
|---|---|---|---|
| `.claude/CLAUDE.md` | Keep rules out of the always-loaded prompt | "References" + "Rules Index" sections *point* at content instead of inlining it | Must keep the index in sync as rules change |
| Path-gated rules | Topic rules that load only when relevant | Frontmatter `paths:` patterns load the body on a matching read/edit; the `CLAUDE.md` Rules Index names them so Claude knows they exist before a pattern fires | Loads on every matching file touch |
| `external-sources.md` | Handle vendored copies, submodules and downloaded source trees safely | Fires on outside code a repo reuses; read and grep it, run it only via a reviewed project entry point | Loads on a matching touch |
| `github-actions.md` | Run workflow jobs locally | Pointer to `github-actions-local-act.md` | Tiny pointer |
| `hooks.md` | Avoid hook-authoring traps (PreCompact, SessionStart, PostToolUse I/O) | Gotcha list; detail in `hooks-deep-dives.md` | Loads on hook edits |
| `prose-budget.md` | Keep unasked-for prose short (docs, docblocks, comments) | Budget + cut list applied while writing | Loads on prose edits |
| `python-refactors.md` | Avoid import/module-structure refactor traps | Gotcha list; detail in `python-refactors-deep-dives.md` | Loads on Python edits |

### References

Read only when a pointer fires.

| Piece | Purpose | How it works | Cost |
|---|---|---|---|
| References | Long checklists/postmortems, on demand | Plain `.md`; loaded only when a `CLAUDE.md` pointer fires | None until triggered |
| `architecture-assessment-gate.md` | Make the refactor-before-feature call deliberately | Checklist loaded once a planning pass decides a refactor-first assessment is warranted | None until triggered |
| `github-actions-local-act.md` | Run GitHub Actions jobs locally with `act`, no Docker-in-Docker | Step-by-step setup | None until triggered |
| `hooks-deep-dives.md` | Hook stdin/stdout contracts in detail | Backs `hooks.md` | None until triggered |
| `instruction-file-discipline-deep-dives.md` | The pre-authorised moves for condensing instruction files | Backs `instruction-file-discipline.md` | None until triggered |
| `mybrain-deep-dives.md` | Rationale behind the `mybrain` design-dialogue steps | Backs the `mybrain` skill | None until triggered |
| `python-refactors-deep-dives.md` | Mechanism + worked example per Python refactor trap | Backs `python-refactors.md` | None until triggered |
| `spec-rework-audit.md` | Check whether a spec review caused re-work | Audit procedure cited by `mybrain-deep-dives.md` | None until triggered |

### Hooks

Runtime guards.

| Piece | Purpose | How it works | Cost |
|---|---|---|---|
| `settings.json` | Wire the hooks | Matcher → script entries | One-time hand-merge |
| `pre-compact.py` | Insurance copy before a compaction | `PreCompact` hook snapshots transcript + plan/todo to a sidecar | Runs on every compaction |
| `post-compact-restore.py` | Re-orient cheaply after compaction | `SessionStart` hook prints the newest snapshot's recovery pointer | Runs on compact/resume |
| `destructive-bash-gate.py` | Block destructive commands prefix-match deny rules miss | `PreToolUse` hook on Bash; recursive `rm` on roots, download-piped-to-shell, writes into `.ssh` → exit 2; writes into ask-guarded paths → ask | Blocks only the matched class |
| `lib/ask_paths.py` | Share `settings.json` ask globs as path matchers | Imported by `destructive-bash-gate.py` from `~/.claude/lib/`; absent → that one check goes inert | None |
| `external-process-test-gate.py` | Keep slow external-system tests out of the default suite | `PreToolUse` hook on Write/Edit of `tests/**/*.py`; docker/browser/HTTP tests must live in `tests/manual/` | Override sentinel for real exceptions |
| `ruff-check.sh` | Stop new lint findings landing | `PostToolUse` on Write/Edit (+ Bash `--lint-only`), re-checked on `Stop`/`SubagentStop`; blocks only on lint counts above the committed baseline | Needs `ruff`; one lint run per Python edit |

### Review loop

An independent second read.

| Piece | Purpose | How it works | Cost |
|---|---|---|---|
| `agents/code-reviewer.md` | Review each finished change in a fresh context | Subagent pinned `opus`/`high`; dispatched with the plan + commit range, never the author's reasoning | One extra agent run per change |
| `agents/*.md` (7 built-in pins) | Route each built-in subagent to a deliberate model | Frontmatter `model:`/`effort:` overrides, e.g. `Explore` → `haiku`/`low`, `Plan` → `opus`/`high` | Copy-in; tune to your plan |
| `agent-model-pin-gate.py` | Keep Agent calls faithful to those pins | `PreToolUse` hook on Agent; blocks a `model` whose family differs from the agent's pin | Blocks only mismatches |

### Skills

A skill's body loads only when you invoke it. The first group is about keeping context small; the
others are general tools I keep around.

### Context hygiene

- `condense` deduplicates `CLAUDE.md`, rules and project docs (spec, plans, runbooks) across the
  hierarchy. Run it when the same guidance has drifted into several files.
- `claude-md-progressive-disclosurer` rewrites a `CLAUDE.md` so it points at long content instead of
  inlining it. Use it when rules are duplicated or keep being ignored; this repo's `CLAUDE.md` got its
  shape that way.
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

### Design and critique

- `senior-architect`: ADRs, tech-stack evaluation, design review, dependency analysis, diagrams.
- `brutal-honesty-review`: blunt critique of code, tests or claims.
- `deep-research`: multi-source web research for questions that need more than one search.
- `architecture-diagram-creator`: HTML architecture diagrams (data flow, components, deployment).
- `mybrain` turns a rough idea into a design by questioning it. Goes with the
  `ideation-techniques-library.md` reference.

### Code quality and dev workflow

- `testing-anti-patterns` catches tests that only test their mocks, test-only methods leaking into
  production code, and mocks set up without understanding the dependency. Use it when writing tests.
- `systematic-debugging` makes Claude investigate before proposing a fix, for any bug, failing test or
  odd behaviour. Pairs with the `anti-patterns-common-rationalizations.md` reference.
- `python-simplifier` simplifies complex Python: smells, duplication, coupling. Not for Django.
- `finishing-a-development-branch` verifies tests, reports branch state, merges into `main` and leaves
  `main` checked out. It never pushes.

### Kaizen

Seven continuous-improvement skills, meant to be copied as a set.

- `kaizen-kaizen` applies Kaizen (small iterations, error-proofing, YAGNI) to one change.
- `kaizen-analyse` picks a method (Gemba, Value Stream or Muda) for a target.
- `kaizen-analyse-problem`: A3 one-page problem analysis, root cause plus actions.
- `kaizen-cause-and-effect`: fishbone diagram over the 6M cause categories.
- `kaizen-plan-do-check-act`: PDCA experiment cycle.
- `kaizen-root-cause-tracing` follows one bug back up the call chain to where the bad value first came
  in. `systematic-debugging` is the broad version; this is the narrow one.
- `kaizen-why`: Five Whys, from symptom to cause.

### Writing

- `detect-ai-text-humanize` either checks whether text reads as AI-written, with reasons per passage,
  or rewrites it to read as human without showing any detection output.

## Glossary

- **Compaction**: Claude Code summarizes a full context window to free space. Reasoning can get lost
  in the summary.
- **Progressive disclosure**: keep detail out of the always-loaded prompt and load it only when
  something triggers it.
- **Path-gated**: a rule that loads only when you read or edit a file matching its `paths:` patterns.
- **Context cliff**: the point where the window is nearly full and the next action forces a compaction.
- **Fan-out**: splitting work across parallel subagents, each with its own context window.
