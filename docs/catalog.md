# Catalog

Every piece in this repo, grouped by what it does. Counts, byte sizes and token thresholds are in the
README's [measured table](../README.md#whats-measured). To copy a piece, see [ADOPT.md](../ADOPT.md).

### Rules - loaded only when a matching file is touched

| Piece | Purpose | How it works | Cost |
|---|---|---|---|
| `.claude/CLAUDE.md` | Keep rules out of the always-loaded prompt | "References" + "Rules Index" sections *point* at content instead of inlining it | Must keep the index in sync as rules change |
| Path-gated rules | Topic rules that load only when relevant | Frontmatter `paths:` patterns load the body on a matching read/edit; the `CLAUDE.md` Rules Index names them so Claude knows they exist before a pattern fires | Loads on every matching file touch |
| `external-sources.md` | Handle vendored copies, submodules and downloaded source trees safely | Fires on outside code a repo reuses; read and grep it, run it only via a reviewed project entry point | Loads on a matching touch |
| `github-actions.md` | Run workflow jobs locally | Pointer to `github-actions-local-act.md` | Tiny pointer |
| `hooks.md` | Avoid hook-authoring traps (PreCompact, SessionStart, PostToolUse I/O) | Gotcha list; detail in `hooks-deep-dives.md` | Loads on hook edits |
| `prose-budget.md` | Keep unasked-for prose short (docs, docblocks, comments) | Budget + cut list applied while writing | Loads on prose edits |
| `python-refactors.md` | Avoid import/module-structure refactor traps | Gotcha list; detail in `python-refactors-deep-dives.md` | Loads on Python edits |

### References - read only when a pointer fires

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

### Hooks - runtime guards

| Piece | Purpose | How it works | Cost |
|---|---|---|---|
| `settings.json` | Wire the hooks | Matcher → script entries | One-time hand-merge |
| `pre-compact.py` | Insurance copy before a compaction | `PreCompact` hook snapshots transcript + plan/todo to a sidecar | Runs on every compaction |
| `post-compact-restore.py` | Re-orient cheaply after compaction | `SessionStart` hook prints the newest snapshot's recovery pointer | Runs on compact/resume |
| `destructive-bash-gate.py` | Block destructive commands prefix-match deny rules miss | `PreToolUse` hook on Bash; recursive `rm` on roots, download-piped-to-shell, writes into `.ssh` → exit 2; writes into ask-guarded paths → ask | Blocks only the matched class |
| `lib/ask_paths.py` | Share `settings.json` ask globs as path matchers | Imported by `destructive-bash-gate.py` from `~/.claude/lib/`; absent → that one check goes inert | None |
| `external-process-test-gate.py` | Keep slow external-system tests out of the default suite | `PreToolUse` hook on Write/Edit of `tests/**/*.py`; docker/browser/HTTP tests must live in `tests/manual/` | Override sentinel for real exceptions |
| `ruff-check.sh` | Stop new lint findings landing | `PostToolUse` on Write/Edit (+ Bash `--lint-only`), re-checked on `Stop`/`SubagentStop`; blocks only on lint counts above the committed baseline | Needs `ruff`; one lint run per Python edit |

### Review loop - an independent second read

| Piece | Purpose | How it works | Cost |
|---|---|---|---|
| `agents/code-reviewer.md` | Review each finished change in a fresh context | Subagent pinned `opus`/`high`; dispatched with the plan + commit range, never the author's reasoning | One extra agent run per change |
| `agents/*.md` (7 built-in pins) | Route each built-in subagent to a deliberate model | Frontmatter `model:`/`effort:` overrides, e.g. `Explore` → `haiku`/`low`, `Plan` → `opus`/`high` | Copy-in; tune to your plan |
| `agent-model-pin-gate.py` | Keep Agent calls faithful to those pins | `PreToolUse` hook on Agent; blocks a `model` whose family differs from the agent's pin | Blocks only mismatches |

### Skills

| Piece | Purpose | How it works | Cost |
|---|---|---|---|
| Skills | Context-hygiene core + config/session/quality/thinking exemplars | Hygiene core (`condense`, `de-bloat`, `claude-md-progressive-disclosurer`, `impag`, `qimpag`); exemplar groups: config & skill mgmt, session hygiene, design & critique, code quality & dev workflow, Kaizen improvement, writing & AI-text | Skill body loads when matched |
| `snapshot` | Save a session by hand | `/snapshot` copies the transcript + plan/todo sidecar into a keep-10 pool automatic snapshots never evict | Loads when invoked |

### Budgets - stop before the context cliff

| Piece | Purpose | How it works | Cost |
|---|---|---|---|
| `docs-bloat-gate.py` | Keep bloated `.md` from entering context | `PreToolUse` hook on Write/Edit/Bash; signals (slop / density / new-audit-file advisory, size ratchet blocks) | Slop/density/new-file warn via a throttled nudge; only the opt-in size ratchet blocks (bypassable) |
| `impag-budget-check.py` | Stop a long run before the context cliff | `PostToolUse` hook on Bash; exact token read; soft FYI heads-ups, then the hard-stop wrap-up | Only the hard-stop band interrupts; the soft bands just nudge |
| `statusline.sh` | Show live context %, cost, distance-to-stop, 5h + 7d limits | Reads Claude Code's statusline JSON; needs `jq` + `git` | Negligible |

The rules `testing.md` (test value gate) and `subagent-dispatch.md` and the reference
`pre-ship-sweeps.md` are general habits rather than context tooling.

## Skills

Skill bodies load only when invoked. The first group is the context-hygiene core; the rest are
general tools bundled because I use them.

**Context-hygiene core** - the leanness toolkit:

- **`condense`** - deduplicate and consolidate `CLAUDE.md`, rules, and project
  docs (spec.md, plans, runbooks) across the hierarchy. The periodic-cleanup
  arm for when the same guidance has drifted into several files.
- **`claude-md-progressive-disclosurer`** - restructure a `CLAUDE.md` so it
  *points* at heavy content instead of inlining it. Reach for it when rules are
  duplicated or keep getting ignored - it's how the `CLAUDE.md` in this repo got
  its lean shape.
- **`de-bloat`** (invoke only via `/de-bloat`) - audit skill files across
  `~/.claude/skills/` and any project `.claude/skills/` for bloat and
  duplication, then emit a plan executed via `impag`. Two passes: a content pass
  (dedupe/compact) and a root-cause pass (which rules/refs/skills drove the
  bloat). Makes no edits itself.
- **`impag`** - implement a plan using parallel subagents, full-auto, never
  stopping to ask. Takes a plan file path (defaults to the newest in
  `docs/plans/`). The fan-out executor the other skills hand their plans to.
- **`qimpag`** (invoke only via `/qimpag`) - questions-first variant of `impag`:
  it launches `impag` unchanged but injects one interactive `AskUserQuestion`
  round once the target plan/stage is resolved, so the questions are grounded in
  the concrete work before execution begins.

**Config & skill management** - the acquisition side of a copy-in catalog:

- **`config-reuse`** - copy or sync Claude configs, rules, and settings from
  another project into the current one; auto-detects the stack.
- **`install-skill`** - install a skill from a GitHub URL or repo path into
  `~/.claude/skills/`.
- **`skills-discovery`** - search for and install a skill that handles the
  current task better than base knowledge.

**Session hygiene** - end-of-session pruning that feeds the leanness loop:

- **`reflect`** - analyze the session and propose skill improvements (only on
  explicit `/reflect`, or from a retro).
- **`retro`** - session retrospective: reflect on what was learned, update
  memories and project docs.

**Design & critique** - general-purpose thinking tools:

- **`senior-architect`** - system-architecture work: ADRs, tech-stack
  evaluation, design review, dependency analysis, diagrams.
- **`brutal-honesty-review`** - unfiltered technical critique when code, tests,
  or claims need a harsh reality check.
- **`deep-research`** - multi-source web research and critical analysis for
  non-trivial investigative questions.
- **`architecture-diagram-creator`** - generate HTML architecture diagrams
  (data flow, components, deployment) for a system.
- **`mybrain`** - refine rough ideas into designs via questioning and ideation,
  before creative or strategic work. Pairs with the
  `ideation-techniques-library.md` reference.

**Code quality & dev workflow** - exemplars for test integrity and branch/debug
discipline:

- **`testing-anti-patterns`** - catch mock-testing, production pollution with
  test-only methods, and mocking without understanding dependencies. Reach for it
  when writing or changing tests or adding mocks.
- **`systematic-debugging`** - structured investigation before proposing fixes,
  for any bug, test failure, or unexpected behavior. Pairs with the
  `anti-patterns-common-rationalizations.md` reference.
- **`python-simplifier`** - simplify or refactor complex Python: code smells,
  duplication, coupling, readability (not Django).
- **`finishing-a-development-branch`** - close out a stage or branch: verify
  tests, report branch state, then merge the work into `main` and leave `main`
  active (merges only if not already on it; never pushes).

**Kaizen improvement** - a coherent continuous-improvement family (all-or-nothing
exemplar set):

- **`kaizen-kaizen`** - apply Kaizen principles (iterative improvement,
  error-proofing, YAGNI) to a specific change.
- **`kaizen-analyse`** - pick a Kaizen method (Gemba / Value Stream / Muda) for a
  target.
- **`kaizen-analyse-problem`** - A3 one-page problem analysis: root cause plus
  action plan.
- **`kaizen-cause-and-effect`** - fishbone diagram across the 6M cause categories.
- **`kaizen-plan-do-check-act`** - PDCA iterative experimentation cycle.
- **`kaizen-root-cause-tracing`** - walk a single bug backward up the call chain
  to where the bad value or wrong decision first entered - the narrow,
  call-stack-tracing complement to `systematic-debugging`'s broad reproduce →
  isolate → hypothesize → verify protocol.
- **`kaizen-why`** - Five Whys: drill from symptom to fundamental cause.

**Writing & AI-text** - detection and rewriting of AI-sounding prose:

- **`detect-ai-text-humanize`** - two modes: Detection (analyze whether text is
  AI-generated, with passage-level highlighting and reasoning) or Humanization
  (rewrite AI-sounding text to read as human, surfacing no detection output).

## Glossary

- **Compaction** - when Claude Code summarizes a full context window to free
  space; load-bearing reasoning can be lost in the summary.
- **Progressive disclosure** - keeping detail out of the always-loaded prompt
  and loading it only when triggered, so unused content costs nothing.
- **Path-gated** - a rule that auto-loads only when you read/edit a file
  matching one of its frontmatter `paths:` patterns.
- **Context cliff** - the point where the window is nearly full and the next
  action forces a compaction.
- **Fan-out** - splitting work across parallel subagents, each with its own
  context window.
