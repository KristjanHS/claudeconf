# claudeconf

## The problem

A long Claude Code session gets slow, expensive, and forgetful. The context
window fills with rule text you rarely need, stale docs, and re-derived state;
once it's full the agent compacts to ~12% of the window - and the reasoning
that lived only in the conversation doesn't come back. You pay for every token
of that bloat on every turn.

## What this is

A **copy-in catalog** of the Claude Code config that keeps a session's context
window lean: a progressive-disclosure `CLAUDE.md`, path-gated rules, compaction
continuity hooks, an anti-bloat write gate, a budget governor, and a statusline
that shows the burn. Each piece is a working example you copy into your own
`~/.claude/` by hand and adapt - **not** an installer.

This is written for someone **already running Claude Code who doubts the
hook/rule/budget sprawl earns its keep.** The honest question - "does this
scaffolding cost me less than it saves?" - is what the rest of this page tries
to answer, including where the answer is "no."

## Does this actually work?

Scoped honestly: the evidence below shows **cost reduction for an existing
Claude Code user**.

**The statusline shows the real number you're spending.** It sums the exact
`input_tokens + cache_creation_input_tokens + cache_read_input_tokens` the API
reports for the turn - the same number the budget governor stops on:

![statusline render](docs/statusline.png)

The bar turns amber and a red `/clear soon` nudge appears as the turn nears the
130k mark - the same threshold the budget governor enforces, so the visual
warning and the automated stop fire off one number:

![statusline near the budget cliff](docs/statusline2.png)

**Progressive disclosure keeps ~8k tokens out of every turn.** The 4 path-gated
rules (~18 KB) and 7 L3 references (~19 KB) total ~37 KB - **~8k tokens**. A
flat `CLAUDE.md` that inlined all of them
would carry that on *every* turn; here they cost 11 deferred-load pointer lines
(7 references + 4 rules) in a 4.4 KB `CLAUDE.md`, and a rule body loads only when
you touch a file its glob matches.

- **The dollars are modest; the window is the point.** Cached, those tokens bill
  as `cache_read`. The real win is the window filling slower, so compaction (which
  keeps ~12% and doesn't restore conversation-only reasoning) comes later.

## What it costs you

A skeptic should weigh the tax, not just the upside:

- **4 hooks fire on lifecycle events** - every compaction, session start, and (for
  two of them) Bash/Write/Edit call runs a Python script. They fail open, but
  they're still latency on the hot path.
- **The bloat gate *refuses* writes.** Two of its three signals (slop phrase,
  low density) are unbypassable - it will block a `.md` write you wanted.
- **The budget governor interrupts.** At 130k tokens it injects a wrap-up
  reminder mid-run, whether or not you were ready to stop.
- **Setup is hand-work.** You merge a `settings.json` hooks block yourself and
  maintain the pytest suite. There is no auto-merge, by design (it's the most
  likely thing to break your config).

## When this isn't worth it

- The bloat gate **false-positives** on legitimately dense writing - a genuinely
  information-rich doc can trip the density floor.
- Some tasks **legitimately need >130k tokens**; the governor's wrap-up nudge
  fights you there. Raise the threshold or skip the hook.
- **None of this helps if you weren't going to run a long agent session
  anyway.** The whole catalog presupposes sessions long enough for context to
  become the bottleneck.

## Glossary

- **Compaction** - when Claude Code summarizes a full context window to free
  space; load-bearing reasoning can be lost in the summary.
- **Progressive disclosure** - keeping detail out of the always-loaded prompt
  and loading it only when triggered, so unused content costs nothing.
- **Path-gated** - a rule that auto-loads only when you read/edit a file
  matching its frontmatter `globs`.
- **Context cliff** - the point where the window is nearly full and the next
  action forces a compaction.
- **Fan-out** - splitting work across parallel subagents, each with its own
  context window.

## The catalog

Every piece and what it's for. Terse by design;
deeper prose for the two mechanisms that don't fit a cell is below the table.

| Piece | Purpose | How it works | Cost |
|---|---|---|---|
| `.claude/CLAUDE.md` | Keep rules out of the always-loaded prompt | "References" + "Rules Index" sections *point* at content instead of inlining it | Must keep the index in sync as rules change |
| Path-gated rules (×4) | Topic rules that load only when relevant | Frontmatter `globs`; harness loads the body on a matching read/edit. The `CLAUDE.md` Rules Index is the *awareness* layer - it names the rules so Claude knows they exist before a glob fires (the harness auto-lists skills this way, but not rules) | Loads on every matching file touch |
| L3 references (×7) | Long checklists/postmortems, on demand | Plain `.md`; loaded only when a `CLAUDE.md` pointer fires | None until triggered |
| `pre-compact.py` | Insurance copy before a compaction | `PreCompact` hook snapshots transcript + plan/todo to a sidecar | Runs on every compaction |
| `post-compact-restore.py` | Re-orient cheaply after compaction | `SessionStart` hook prints the newest snapshot's recovery pointer | Runs on compact/resume |
| `docs-bloat-gate.py` | Block bloated `.md` from entering context | `PreToolUse` hook on Write/Edit/Bash; 3 signals (slop / density / size) | Refuses writes; 2 signals unbypassable |
| `impag-budget-check.py` | Stop a long run before the context cliff | `PostToolUse` hook on Bash; exact token read, hard-stop at 130k | Interrupts mid-run at the threshold |
| `statusline.sh` | Show live context %, cost, distance-to-stop | Reads Claude Code's statusline JSON; needs `jq` + `git` | Negligible |
| `settings.json` | Wire the 4 hooks | Matcher → script entries | One-time hand-merge |
| Skills (×15) | Context-hygiene core + config/session/thinking exemplars | Hygiene: `condense`, `de-bloat`, `claude-md-progressive-disclosurer`; executor: `impag`; config/skill mgmt: `config-reuse`, `install-skill`, `skills-discovery`; session hygiene: `reflect`, `retro`; design & critique: `senior-architect`, `brutal-honesty-review`, `deep-research`, `architecture-diagram-creator`, `mybrain`; standalone: `detect-ai-text-humanize` | Skill body loads when matched |
| `.claudeignore` | Keep archived plans out of context | Lists paths the harness skips | None |

## The budget governor (detail)

`impag-budget-check.py` is a `PostToolUse` hook on `Bash` that makes a long
`/impag` run stop taking new work before the session hits its context cliff. It
reads the **exact, compaction-aware** token count from the transcript tail
(no estimate, no dependency) and hard-stops at 130k: silent below, a wrap-up
reminder at or above. It fails open - any error exits 0 and never blocks a
commit. Why it and `statusline.sh` are pinned to the *same* 130k mark and
measurement is explained in
**[`.claude/hooks/README.md`](.claude/hooks/README.md)**.

## The skills (detail)

Fifteen `/<name>` skills ship in `.claude/skills/`. The first group is the
context-hygiene set this repo is really about; the rest are bundled exemplars
across config management, session hygiene, and general thinking tools. Skill
bodies load only when you invoke them, so they cost nothing until used.

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

**Design & critique** - general-purpose thinking tools, outside the
context-engineering theme:

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

**Standalone exemplar** - outside the context-engineering theme:

- **`detect-ai-text-humanize`** - two modes: Detection (analyze whether text is
  AI-generated, with passage-level highlighting and reasoning) or Humanization
  (rewrite AI-sounding text to read as human, surfacing no detection output).

## Quick start

```sh
git clone https://github.com/KristjanHS/claudeconf
cd claudeconf
```

Then see **[ADOPT.md](ADOPT.md)** for how to copy each piece into your own
`~/.claude/`.
