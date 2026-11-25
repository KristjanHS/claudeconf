# Memory system — layer roles, write targets, graduation, budgets

Single source of truth for what each memory layer IS, who adds vs. prunes it, where retro's writes route, and graduation; `CLAUDE.md`, `recording-principles.md`, and the `impag`/`retro` skills point HERE and keep only their trigger-time procedure. **No layer has a size cap or a byte gate** (all removed 2026-07-25 — they bought nothing and cost repeated trim passes); each is governed by what it may ADMIT: the Roles table's *Content test* + §Rolling state's delete classes. Navigate this file by grep (`grep -n '^##'`), read only the needed section — never full-read.

## Roles table

| Layer | Role | Content test — admit ONLY this | Adds | Prunes |
|---|---|---|---|---|
| `MEMORY.md` | Stable index — one hook line per file. Never state, never a log. | one line per existing memory file, a stable hook — no state, no prose the file itself holds. (Claude Code silently drops past ~200 lines — issue #39811 — so an index that long means files that should have graduated out or been deleted.) | any memory write (its index line) | writers at write time |
| `project_state.md` | Volatile live pointer — next action + chain/sentinel state + *active-task* USER-owed + one-line pointer to roadmap `§OWED[USER]`; the shipped-feature eyeball backlog lives in roadmap, never here. | the ONE armed item + chain/sentinel state + active-task user-owed + a one-line roadmap pointer. Nothing shipped, no evidence, no second `▶`. | **impag** — sole *reconciling* writer (once/turn, wrap-up boundary) — **+ any session's finish-report** (append-only mirror of a non-empty `Needs you:` do-next line into "Next action") | writers at write time (wrap-up append lands over is fine); overage surfaced at session start by `session-start-health.py` |
| memory `roadmap.md` | Overflow of project_state — volatile menus (open-work, cross-project + deferred follow-ups) **and the sole home of the `OWED[USER]` backlog**. Read on demand, pulled scoped; only its `MEMORY.md` pointer is always-loaded. Durable knowledge graduates OUT to a domain reference / edit-site. | selectable open work, gated plans, `§OWED[USER]`, low-pri NTHs — one bullet per item, its doc named rather than summarized. Never size-swept. **An NTH enters only as work someone would pick off this menu; a review finding already ruled not-worth-doing is dropped, not down-routed here.** | impag (same burst as project_state) **+ any session's finish-report** (`Needs you:` eyeball/decision → `§OWED[USER]`) | writers at write time only (no sweep, no subagent) |
| `type: feedback` file | Staging for a behavior steer (frontmatter is the key; existing files carry a `feedback_` prefix, not required) — a graduation TODO, not a home. | one steer per file, phrased so it can be pasted into its target rule/skill — drain, never grow. | recording-principles routing; retro Step 2 | retro graduation (§Graduation routing) |
| `references/*.md` (L3) | On-demand deep detail behind an L1/L2 pointer; costs only when a pointer fires. Accumulates one-directionally — dead-pointer/absorbed files are deleted. | detail an L1/L2 pointer actually promises, greppable by `##` section. A section no pointer names is dead — delete it or split the file by TOPIC (never by size). | recording-principles routing | writers at write time |
| `.claude/rules/*.md` (L2) | Path-gated operational rules — the generic habit, never the incident. | the three-line canonical body (§Write targets): rule / **Why** / **How to apply**. Dates, SHAs, `file.py:123` and one-project incidents belong to the commit message. | retro Step 4 | writers at write time; user-run `condense` |
| project architecture doc + gotchas ledger | Durable project facts (map, seams, contracts); the ledger stages facts not yet at their edit site (§Graduation routing). | facts that survive between sessions and have no single edit site. "Currently"/"next" prose belongs in auto-memory; a fact with ONE home goes to that home, not the ledger. | retro Step 3b | writers at write time; user-run `condense` |

### MEMORY.md vs project_state.md — never mirror

**Generally: a fact that owns a memory file is cited by `[[link]]`, never restated.** A `Status lines` / `Pointers out` block re-stating what `[[vercel-ops]]`/`[[local-supabase]]`/`[[release-chain]]` or the MEMORY.md index already say is a mirror — always-loaded twice, updated in one place only. Same for the pointer's frontmatter `description:`: a stable descriptor, not a copy of CLAUDE.md's mission prose.

MEMORY.md is the STABLE index, project_state the VOLATILE pointer. MEMORY.md's line for project_state must be a **stable descriptor** ("live pointer — current task + chain state; read on resume"), never a copy of Next-action prose (SHAs, stage numbers) — mirroring volatile state means two places to update and an index stale between sessions. A MEMORY.md that keeps growing is usually indexing files that should have graduated out (feedback → skill/rule) or been deleted (closed verdicts) — prune those files and the index shrinks with them.

## Rolling state — project_state / roadmap

**Nothing here is size-managed. The whole discipline is admission: the cheapest line to prune is the one never written.** Before writing a line, route it — armed-item state → project_state; selectable/gated work, `§OWED[USER]`, NTHs → memory `roadmap.md`; durable facts/gotchas → a domain reference or the edit site (retro Step 3b); evidence, rationale, measured tables, "why we chose this" → the plan doc or the commit message, which the pointer then names in ≤1 line. A line that fails routing is not written smaller — it is written elsewhere, **or nowhere: dropping is a routing outcome and the most common correct one.** Every destination named above is a file, so "route it" silently reads as "file it somewhere"; the terminal sink is `git log`, which already holds anything no future session must be *told*. Ask "which file?" only after "does this need to exist at all?" has been answered yes. **A line that passes routing is still capped at two lines and must be a value, a move or a falsifier** — `~/.claude/rules/prose-budget.md`, which the memory path does not auto-load (the slug path `~/.claude/projects/<slug>/memory/` is outside the project tree, so its `paths:` gate never fires there — even on a linked project, where that dir is a symlink into `<repo>/.claude/memory/` and only an edit addressed by the repo path would fire it).

**impag is the sole *reconciling* writer** (once/turn at a wrap-up boundary): it appends new state AND reconciles existing live items — each carries a cheap falsifier (`migration list`, `git log --grep`, live-artifact check); any the check proves closed is dropped/rewritten in the same burst, so out-of-band state (deploys, user actions, other sessions) doesn't outlive its truth. Sole-*reconciling*-writer, not sole writer: **any session's finish-report append-only mirrors its non-empty `Needs you:` items in** (do-next for the armed item → "Next action", anything else → roadmap `§OWED[USER]` / menu); impag reconciles/dedups them next wrap-up. A subagent never writes project_state — it races the wrap-up and clobbers the sentinel. At every write the delete classes below apply and sentinel + "Next action" stay intact; finished-stage narrative is deleted, not demoted into an archive section (git + archived plans hold it). The roadmap is NOT append-only; readers pull it scoped, live content on top.

**Write-time delete classes.** The reconcile bound limits falsifier *runs*, never deletions — and no file is "small enough" to be entitled to dead weight. **Carry-forward is a write:** the full-body rewrite re-emits every old line, so each one re-faces the writer's admission test and these classes — a line that only ever passed an *entry* test at birth is how a pointer decays into a log. Drop at EVERY write, no falsifier needed:

1. **Shipped/ruled recaps** — including the "SHIPPED+REVIEWED `<sha>`" *preamble* of a bullet that keeps a live OWED tail: strip to the owed line, rephrased as pending. A terminal/parked stage has no successor commit to trigger delete-now — delete on ship.
2. **Detail a git-tracked doc records** — the resume payload is `doc §N` plus only deltas not yet in any doc. A ruling "recorded in spec §4" means delete the restatement — its constants, commands, trap warnings, and falsifier greps ride along (the doc holds them). **A CODE DOCBLOCK is a git-tracked doc.** A fact already graduated to its seam is the most-missed case of this class: it reads as durable and un-homed, so carry-forward keeps it forever beside the copy that governs. Before carrying a code-shaped fact, grep the SOURCE tree for the symbol it names — `docs/` and `rules/` alone will not find it.
3. **Meta-instructions** — a header restating this file's routing rules or the impag contract. State files carry facts, never instructions: the writer's contract lives in the SKILL and here; an in-file guardrail is re-billed every session and drifts from the canonical text it copies.
4. **Expired dated lines** — a claim with a passed self-expiry ("heals on next cron", "until \<past date\>").
5. **Surplus ▶ items** — "Next action" holds ONE armed/in-flight item; other selectable work is the open-work menu (→ roadmap), decision-gated items are `§OWED[USER]` (single home). A multi-▶ section IS the menu that was routed out.

Spend emphasis (caps/⛔/bold) only on lines meant to change the next session's behavior — uniform alarm reads as none.

**The classes have a detector; they are not self-enforcing.** `session-start-health.py` check (f) notes at session start when `project_state.md` carries a `##` section this file's Roles table does not admit. It measures nothing — a long file whose sections are all admitted stays silent — and it exists because a 52k `project_state.md` (2026-08-01) grew `## Other open work` and `## Live code constraints` while every class above already forbade both.

**It is an FYI, never a task, and never a blocker.** Do NOT open a shrink/relocate pass in response to seeing it: route the stray section at the **next write to that file**, or leave it for a user-run `condense`. Acting on it immediately is the cost that retired the old size band — a notice at session start reads as a work item, and the turn's entire output becomes moved prose. The check fires **once per distinct drift state** (sentinel keyed on the stray-heading set) precisely so it cannot pressure a later session into "fixing" it; a repeat sighting is impossible unless a NEW unadmitted section appeared. **Read a fire as a routing failure, not a licence to add rules:** the eventual fix is deleting the section and routing its content, never appending a class that restates one of the five.

## OWED lifecycle

An `OWED[USER]` item is a visual/manual confirm with **no automatable falsifier** — the reconcile machinery (§Rolling state) keys its *drop* decision on a runnable falsifier, which a human eyeball lacks; left unhandled, a closed eyeball gets hand-annotated but **never removed**. Two rules:

- **Single home.** The OWED[USER] backlog lives in **exactly one place — memory `roadmap.md §OWED[USER]`**. project_state carries only *active-task* user-owed lines plus a one-line pointer — never a backlog copy: two homes desync, a close applied to one never propagates, and the mirror accumulates stale OWED. **Splitting it into its own file(s)** (`eyeball.md`/`blocked.md`-style judge/do-decide split) is the same defect at file granularity — an outside-Roles-table fragmentation finding; fold it back into `§OWED[USER]`.
- **The verdict IS the falsifier.** The close signal is a **recorded USER verdict** in a chat turn — at the next write, a user-confirmed/resolved item is annotated and **dropped in the same burst**. A struck / RESOLVED / confirmed / verified OWED line is a **delete-now marker, not a keep-state** — same for any completed roadmap/state item: delete the bullet outright, never a "DONE (don't re-flag)" tombstone (git + transcript are the record; a forward-looking consequence is a NEW live item phrased as pending). An *un*-annotated OWED item is legitimately kept (no verdict yet ≠ "missing falsifier" defect); no git/artifact falsifier may be demanded of it.

## Write targets

Loaded on demand from retro Step 3/4 when there's something to write.

**Global targets are stow symlinks — Read AND Edit the canonical path.** Every `~/.claude/rules/*.md` and `~/.claude/references/*.md` (incl. paired `-deep-dives.md` files) is a stow symlink; Edit/Write refuses to write through it. Use `~/projects/dotfiles/claude/.claude/<rel>` directly, and `Read` *that* exact path before editing (Read tracks by path; a `~/.claude/` Read never satisfies the canonical Write). Don't attempt the `~/.claude/` path first.

### Canonical rule body — two lines, plus a conditional third

Use for new bullets and any rule body rewritten this retro; don't proactively rewrite conformant rules.

- *Rule statement* — imperative, one line — REQUIRED
- **How to apply:** trigger condition (when/where it fires) — REQUIRED
- **Why:** the reason (invariant, incident-class, constraint) — **only when the rule statement doesn't convey it** (`instruction-file-discipline.md` §anti-pattern 1). A Why written to fill the template is the bloat that anti-pattern names; two lines is the normal body.

Incident dates, commit SHAs, `file.py:123` refs belong in the **commit message**, not the rule body; "Exact text" proposals must conform. Avoid in rule bodies: hyperbole, vague instructions, historical comments, duplication.

**Decide the tier before you strip.** Those markers (date, `file.py:123`, project-only path) are what `instruction-file-discipline.md` §anti-pattern 3 routes on — strip them first and a one-project incident is laundered into universal-sounding prose, lands in a **global** rule, and path-gate-loads for every project forever. Order: (1) hold the raw incident; (2) name a second project the rule would fire in — if you can't, the target is `<project>/.claude/rules/<topic>.md`, **created if absent** (a missing project rule file is not a licence to append global); (3) only now move the markers to the commit message.

Grep the file *before* appending (`instruction-file-discipline.md` §anti-pattern 2) — a near-duplicate is a merge, not a new bullet.

**Retro never condenses an instruction file or doc.** For CLAUDE.md, `rules/*`, `references/*`, SKILL.md and project docs, **size is not a trigger — there are no caps to be over** (§No size caps); condensing them is a user-run `condense` pass with per-item approval. Two things are NOT condensing and still run automatically: **auto-memory write-time pruning** (each writer drops the delete classes from its own `project_state.md` / `roadmap.md` / `MEMORY.md` at the write — §Rolling state; impag owns the project_state wrap-up write) and **routing an entry to its durable home** (§Graduation routing, or rolling-state overflow into `roadmap.md`).

### Archive closed plans

Plan COMPLETE, follow-ups closed/tracked elsewhere: (1) `git mv` into `<project>/docs/plans/archive/` — the whole mechanism (plans are never auto-loaded; `.claudeignore` is unimplemented, anthropics/claude-code#4160); (2) drop the plan's stale narration from auto-memory — the archived doc + git preserve it.


## Graduation routing

### `type: feedback` files — capture → graduate

A behavior steer captured to memory is a **`type: feedback`** file — the frontmatter identifies it (the drain matches on type; existing files carry a `feedback_` prefix but new ones need only the frontmatter). It only reliably changes behavior once it's IN the target skill/rule/CLAUDE.md body (a memory file is merely recalled *if* judged relevant). Graduate as soon as the target is reachable → **delete**; what can't graduate stays, swept every retro (retro-owned, coupled to Step 2 capture): graduate+delete, or re-affirm pending **with a one-line reason** (surviving two retros unexplained = accumulation smell; force the decision). Stranger test first: a steer about skill behavior (impag/qimpag/retro/…) is **GLOBAL** → the global skill/rule, never project memory. Index under a `Feedback (pending graduation)` heading in MEMORY.md, never inline with durable knowledge.

### Gotchas ledger — a staging area, not a home

A `Load-bearing gotchas` / `Lessons` section in a project architecture doc is `feedback_*` for architecture facts: a graduation TODO. Every entry is *individually* true and non-obvious, so no "drop superseded prose" sweep shrinks it; it is the purest asymmetric-verb bloat (`instruction-file-discipline.md §Write-time checks`): retro Step 3b files in every session, nothing files out. The fix is at the filing step, not a later sweep:

- A fact with **one** edit site never enters the ledger — it goes to the seam (code comment, path-gated rule, domain reference); the ledger holds only facts spanning ≥2 seams with no single home. Most candidate entries fail this test, so the normal outcome is filing nothing.
- **Filing a new entry graduates an existing one out in the same burst** — pick the entry whose edit site is now obvious. One in, one out, at every filing.
- Graduating edits code, so it is *propose-only* for a dispatched subagent; the parent applies it.
- **The same doc's coverage rows (a file inventory, a `~`/`✓` freshness table) are a cache with an admission rule and no eviction rule.** "Upgrade `~` to `✓` when a task touches those files" is two add-verbs and no subtract. Pair it: **a row a refactor invalidated is DELETED, not marked stale, and a `~` row a touch shows to be wrong is DELETED, not downgraded** — the seam moved, so the row describes a file layout that no longer exists and no later reader can tell. Deleting is also cheaper than re-deriving the correct row, which is what a "stale" marker silently defers forever.

## No size caps — admission instead

**There are no byte caps, line caps, entry caps or percentage gates on any memory file, rule, reference, SKILL.md, CLAUDE.md or project doc** (all removed 2026-07-25). Size is never a reason to edit a file, never a trigger, and never something to measure: `wc -c` on an instruction file or doc is not a step in any workflow. Rationale: the caps produced recurring "over the gate → plan a cut set → trim → re-measure" passes whose entire output was moved prose — a large, repeated token cost for zero behavior change, and they pushed writers into compressing lines that should never have been written.

What governs each file instead:

- **What it admits** — the Content test per layer (§Roles table), under the universal admission test (`prose-budget.md` §Every add pairs with a delete).
- **What it must drop at every write** — the delete classes (§Rolling state): shipped/ruled recaps, detail a git-tracked doc records, meta-instructions, expired dated lines, surplus `▶` items. These are content judgements needing no measurement, and they apply to carried-forward lines too.
  ⛔ **The delete classes are AUTO-MEMORY-SCOPED by design** — `project_state.md`, `roadmap.md`, `MEMORY.md` and nothing else. A **git-tracked doc's drain lives in that doc's own write rules**, paired to its own add-verb's trigger (`instruction-file-discipline.md` §Write-time checks — Symmetric verbs). Neither regime covers the other, and a doc governed by neither grows without bound: that gap is what let three git-tracked docs fall between them.
- **Navigation, where a file is genuinely long** — unique greppable `##` headers; readers `grep -n '^##'` and read one section. Long-but-navigable is fine; that is what on-demand files are for. Split a reference by TOPIC when a pointer would otherwise drag in unrelated sections — never because of its size.
- **`MEMORY.md`'s one external constraint** — Claude Code silently drops the index past ~200 lines (issue #39811). That is a harness truncation fact, not a style budget: if the index approaches it, the fix is deleting/graduating the files it indexes, not compressing hooks.

**One named carve-out**, and it sits inside a user-run pass rather than measuring a file to decide whether to open it: `condense`'s **§Section-size flagging** extends to every trigger-indexed L3 doc, where a >1500-char section is a dedup *candidate* surfaced for per-item approval. The sentence above holds everywhere else: size is not a trigger and not something to measure.

**Nothing gates size or slop.** `docs-bloat-gate.py` S2/S3 log an advisory nudge and the write proceeds; the only control is admission discipline. Sizes on demand where a project offers them (`make docs-report` in dotfiles — advisory, always exit 0).

**Prune subagents: do NOT touch `roadmap.md` or `project_state.md`.** **Never condense a skill mid-run.** Deliberate consolidation is a user-run `condense` / `de-bloat` pass with per-item approval, driven by duplication and staleness — not by size.
