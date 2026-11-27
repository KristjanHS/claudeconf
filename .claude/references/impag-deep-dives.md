# impag — deep dives

Long-form rationale, evidence, and conditional/abnormal-only sub-procedures for the `impag` skill. The body (`impag/SKILL.md`) holds **every normal-path directive** — including the chaining/sentinel directives;
this file holds only the *why*, the token-efficiency evidence, and the conditional modes (research-style plans, code-reviewer fallback, deferred review).
**Read it only when a step points here or an abnormal condition is met** — nothing here repeats a body directive. **Charter test before adding a section: would a normal run open it to proceed? Yes → it belongs in the body** (`rules/instruction-file-discipline.md`); that test evicted branch-pruning and the plan-authoring sequence on 2026-07-25. A normal single-session code-plan run never needs this file. **Read SCOPED**: `grep -n '^## '` for the section the body pointer names, then Read only that section — never full-read. Split into topic files when a pointer would drag in unrelated sections — by topic, never by size (`memory-system.md §No size caps`).

---

## Step 1 — uncertainty markers (rationale)

Why surface the plan's author-acknowledged hedges (`[AUDIT]`, `[likely cut]`, "not sure whether") before Stage 1: the plan author's own doubt is the strongest "don't ship yet" signal available — don't ship past it silently.

## Step 2 — never ask to defer (rationale)

Why the agent picks no stopping boundary up front and never asks the user to choose one: take in as much work as fits, and let the wrap-up limit — not an interactive prompt — decide where the run ends.
Don't burn a turn asking "Stage A now, Stage B later?"; that's the hook's job, not the user's.
The stop lands at the most recent clean stage boundary (defined in body step 2), so a resume never lands mid-task.

## Step 3 — stay where you were launched (rationale)

Why the no-branch / no-worktree / no-`cd` rule: the user decides where Claude runs (the main checkout or a worktree they set up) and on which branch; the agent stays exactly where it was put.

## Step 3 — delegate only when it pays (rationale)

Why direct edit is the default and a sub-agent must clear the gate: a sub-agent re-pays the full system-prompt + `CLAUDE.md` + file-read startup tax on every dispatch (agents ≈4×, multi-agent ≈15× the tokens of a plain edit — Anthropic's multi-agent-research figures),
so delegation only wins when context isolation or genuine parallelism outweighs that tax.
Full findings → `docs/subagent-delegation-findings.md`.

**Cost lens (governs every gate criterion — moved here from the body 2026-07-12 to cut per-task re-reasoning).**
A subagent re-reads its files from zero — no share of the parent's prompt cache — so it pays only when `reads-kept-out-of-parent × remaining-turns > its one-time re-read + brief`.
Files already in the parent's context ⇒ edit inline (delegating re-reads what the parent already paid for);
a fresh read the parent doesn't yet hold is NOT "reused" by inlining — delegating sends the edit into the subagent with it, so those bodies never enter the parent (exactly what gate (a) buys).
The deeper the session the more this pays; early session only weakens it, never flips (a) to inline when large unheld reads sit behind the edit — no matter how many files that edit spans.
**Single-big-acquisition case (why (a) isn't just a file count):** even ONE big throwaway reference / deep derivation (a 46 KB mockup ported into `public/*`, a constant derived across files) feeding the edit should delegate to return just the result —
the file-count threshold misses it, but that read re-bills every remaining turn of a multi-task run.
**Why a multi-file edit does NOT buy a direct pass (reversed 2026-07-13 at N=2 — incident below):** the old gate let 4+ files-to-edit stay direct even behind many large unheld reads, reasoning a subagent could budget-cap mid-edit and strand a half-applied change.
But an inline read-sweep that budget-caps is *worse* — it poisons the whole chain's context (re-billed as `cache_read` every remaining turn), whereas a subagent's cap loses only its own throwaway context.
So the count that governs (a) is **large unheld READS, not files to edit**: a stage needing several large unheld reads is too coarse to hold — delegate it (or split the plan stage).
**(d) grounds a plan-contract with a brief even when the orchestrator writes the plan itself** — anchors + signatures + conflicts enter the parent (brief it to lean on the architecture-overview doc per step 1b, greping only gaps); the byte-exact port belongs to the chained execution session, not the planning one.

**Why a dispatch is sized to ONE committable slice** (body: "not the whole multi-slice stage"): a pinned-default implementation subagent caps at ~one slice of recon+edit+verify (measured on opus/medium); a multi-slice dispatch budget-exhausts mid-stage.

**Why the brief's wording is strict:** a per-task commit on `main` is shippable the moment it lands, so a lint deferred to step 6 first fires at the release; `&& git commit` after a `| tail` gate commits a red suite because the pipe exits with tail's status; the falsifier clause is pasted verbatim because a reference the orchestrator has read does NOT reach a subagent.

## Step 3 — research-style plans (conditional mode)

For plans that are web research / analysis / docs with no code:

> **Research-style plans** (web research, analysis, docs — no code): dispatch each analysis task with `subagent_type='general-purpose'` (its pinned default) and have it invoke `deep-research` first. **Not `Explore`** — it pins to `haiku`/`low` and its own description says don't use it for open-ended analysis; reserve it for *locating* sources, then hand the list to `general-purpose`. Skip step 4's test/type-check gate and step 6's code-reviewer. Commit one consolidated doc.

## Step 6 — deferred plan-scheduled review (conditional)

When the plan schedules ONE full-range review at its final stage and a budget wrap-up fires before that stage, SKIP the session review and defer to the plan's — record the deferral + the full `BASE..HEAD` range in project_state (don't double-review per session). Before the eventual dispatch, RE-MEASURE the deferred range to the plan's OWN commits: a recorded range accretes sibling plans' work that landed meanwhile and was already reviewed at its own boundary. Grep the log for the stage's unique SYMBOL, never a commit number.

## Step 6 — code-reviewer fallback (conditional)

> If `code-reviewer` is not a registered subagent type, announce the gap ("code-reviewer not available — dispatching `general-purpose` with a review prompt"), fall back to `general-purpose` (its pinned default) — **not** `Explore`, whose effort pins to `low` and whose own description says don't review with it.
> Over a committed range, `/code-review` adds an independent verify stage the single agent lacks (it alone can mark a finding REFUTED); benched against `code-reviewer` on 2026-07-09 it bought **no extra recall** at ~14× the tokens,
> and it is gated `user-invocable-only` — suggest it to the *user* to filter false positives, never invoke it yourself to widen the net.
> Record the registration gap in the retro. Don't silently degrade.
>
> **A deferred-review BASE SHA is a claim, and it rots exactly like a line cite.** A review deferred by plan design accumulates unrelated waves behind its recorded base — one reached 271 commits / 206 files / 40k lines before anyone re-measured. Before briefing a reviewer, run `git log --oneline <base>..HEAD | wc -l`; a 3-digit count means the base is **wrong**, not that the diff is big. The fix is body step 6's RE-MEASURE directive.

(Step 8's prune-fully-merged-branches how-to and the permanent-branch report shape are **inlined in the body** — both are normal-path how-to every finish needs, so an L3 split saved nothing. Moved 2026-07-24 / 2026-07-25.)

## Steps 1/3 + Rules — token-efficiency levers (evidence)

2026-07-02 crash-dash qimpag retro: a planning-only pass hit 149k context in 14 min / 30 API calls (~3.26M cumulative cache-read — inflated, and *not* the dominant cost; see the 2026-07-09 correction at the end of this paragraph).
The questions round cost only ~8k; the budget went to recon-in-parent and full-doc reads: full Read of the growing multi-stage design doc +14.7k (a later 4.3k `grep -A40` of the same doc proved sufficient), full `roadmap.md` read +4.3k just to pick one item, inline plan-authoring recon +16.3k, and post-commit test recon +17.1k whose only deliverable was a 488-byte roadmap note.
These drove step 1's scoped plan-load, gate clause (d), and the two late-session/per-stage Rules bullets.
That tension (`/retro` on a ~142k context adds ~8k more at peak) is resolved as of 2026-07-16 by step 9's budget-deferral: past the 4f zone, retro is owed via project_state's Next-action and runs at the next chained session's small prefix. Step 9 is also capture-gated the same date: only a concrete capture item earns a retro — stage-done/task-count alone never do.
Separate observation from the paired 2.5-h impag session: ~360k tokens of cache re-creation from TTL expiries during long user-latency gaps — pacing, not a skill defect.
Two more data points behind the same levers (moved here out of the always-loaded body): an earlier full modes-and-markets recon in the parent cost **~7M** billed tokens re-discovering cacheable seams/constants — the extreme case driving step 1b's "read the architecture doc, brief `Explore` to grep only the gaps";
and a C3b qimpag planning pass hit **~155k vs ~90–100k** purely from inline-reading ~1k lines "to be sure of the port" — reads that re-bill as `cache_read` every turn (behind the late-session / per-stage recon Rules bullets).

**2026-07-10 crash-dash execution chain — the round-trip, not the payload.** 62 logical assistant messages, 58 issuing tools: **51 fired exactly one tool call and none fired 3+.**
Recon content was already lean — 46k chars of Bash output over 45 calls, 7 of 9 Reads used `offset`/`limit`, no file read twice — yet `cache_read` reached **16.8M tokens (43% of the bill)** against `output` at 187k (24%).
The driver is `Σ prefix over calls`: context grew 0 → 161k with **no compaction** (`isCompactSummary` count 0), so an identical probe at message 62 re-billed 161k where the same probe at message 2 re-billed 42k — **3.8× for arriving later**.
Batching the clearly-independent runs (four consecutive fixed greps at msgs 4–7; three separate `wc -c` size probes at the stage end; two adjacent `scoring_constants.json` diffs) saves ~8–12 of 58 calls ≈ **6% of the bill** — real, but **not** the ~16% CLAUDE.md headline, because most of impag's loop is *genuinely* sequential-dependent (regen → verify tree; grep → windowed read at the line it found).
Two payload-side findings from the same run: a bare `git diff` (7,804 chars) issued immediately after a `git diff --stat` put the session's largest dump into the prefix at msg 4 and re-billed it on ~58 later calls ≈ **13k tokens for one command** — step 4a already bans this, and it was violated;
and `git show HEAD:calibration.json` was re-shelled inside **five** separate python blocks instead of cached once.
Lever ordering at impag's context depths: (1) fewer round-trips, (2) smaller prefix, (3) fresh reads off the main thread. Trimming per-call output moves nothing.

**2026-07-09 correction (measured, 32 sessions).** The token figures above were summed per JSONL record, but Claude Code copies `message.usage` onto *every* content block, so per-record sums over-count API calls and tokens by ~3.4× — dedupe by `requestId`.
Re-measured, the bill is ~35% cache_read / ~33% cache_write / ~30% output: cache_read is the largest line but **not** "the dominant cost", and ~73% of output is unpersisted reasoning (so trimming prose caps out at ~2.4%).
The TTL-expiry observation above is **confirmed but small** (~1.6% of the bill); most cold prefix re-writes come from mid-session prefix mutation (`ToolSearch` schema fetches, `Skill` body injection), not idle gaps.
The levers these bullets drive — scoped reads, subagent delegation, low-context stopping points — all survive; only the "cache_read dominates" framing was wrong. Full model → `~/projects/dotfiles/docs/research_results/context-cost-model.md`.

## Rules — late human-input pause (cost math)

Why a late `AskUserQuestion` is a *stop*, not a wait: the prompt cache has a 5-minute TTL, so an answer arriving after it lapses re-writes the whole prefix at `1.25×` instead of reading it at `0.1×` — `context × 1.15` billed tokens.
~46k at a 40k front-loaded round; **~150k+ once past the step-4f zone** — an entire extra session's prefix, spent to ask one question.
The chain machinery makes stopping free (write the question to `project_state`'s "Next action", un-arm the chain, resume fresh at a small prefix) — precisely what holding a warm prefix open is not.
The steps 4b/5/7 escalations stay legitimate; only their *shape* changes past the step-4f zone. Full model → `~/projects/dotfiles/docs/research_results/context-cost-model.md`.

## Step 3 — execution recon needs the same bound (evidence)

Recognition cue: a rotted line-cite tempting a subsystem re-read = the banned pre-implementation sweep — re-anchor with one grep + a narrow window, never a sweep.

2026-07-04 crash-dash qimpag session — the chained *execution* session, not a planning one — spent its entire recon budget (~150k tokens, two wrap-up warnings) tracing a 7-file symbol chain (`resolveCuts`→`indicatorReadingSeries`→`ownSeriesZ`→`calibratedZ`→`confirmedSeries`→`CALIB_MAP`→an unrelated `CREDIT_WARMUP`) to derive one padding constant `LOOKBACK_PAD` by hand — and never landed a value;
it punted the decision to `project_state` for the next session, so the research cost was paid and the decision *still* wasn't made, with all of it in the main loop (re-billed as `cache_read` every turn).
This is why "Contract/planning recon ≠ execution recon" isn't the whole story: execution recon needs a bound too, just applied to *implementation-correctness* (grep + narrow window → edit; pick-and-test) instead of *contract grounding* — this WAS the chained execution session and it still blew the budget on research alone with zero code written.
The one-sided-verifiable caveat is from the same case: a too-large `LOOKBACK_PAD` passes the left-edge-fidelity test silently, so "let the test decide" needs a sanity bound for padding/lookback constants.
Root cause driving fix-at-planning: the plan cited `LOOKBACK_PAD` with **no value**, stranding an underdetermined numeric decision into execution — step 1's hedge clause now treats an unspecified constant as a plan hedge to resolve at author time.
*(Graduated 2026-07-13 at N=2. Second crash-dash execution session, same failure: a "hold the context" direct-edit call on Stage 4 pulled a full-subsystem inline sweep — all of run.ts + notify_format.ts + alert-band.ts + two ~2900-line test surfaces — climbing 48k→130k before a single commit landed.
Fix: the delegation gate now leads with "the READ is the cost" and reverses the "4+ files ⇒ direct" override — grounding that needs large unheld reads delegates; inline recon is kept to three exceptions (already-held / bounded grep-window / short-file-being-edited).)*

---

## project_state — full mechanics

The body keeps the snapshot definition (never-a-SHIPPED-log, pointer-only with overflow to the memory `roadmap.md` file, written once per turn, the visible sentinel block). These are the mechanics it points to:

**Write discipline — why batch, never dribble.** Nothing resumes mid-stage, so per-task writes are wasted churn — the commit log is the per-task record. (The once-per-turn / at-a-wrap-up-boundary / whole-burst mechanics are in the body.)

**Reconcile scope — advanced items + cheap falsifiers, not an exhaustive sweep (capped 2026-07-12).** The body caps each wrap-up reconcile to the items being advanced plus any live claim whose falsifier is a one-liner already in hand (`git log --grep`, a `migration list` just run).
It does NOT force fresh recon over every roadmap item each write — that scaled wrap-up *reasoning* with roadmap size (measured: ~9k output on one wrap-up re-deriving all live claims, crash-dash `eb55c849`, where reasoning was ~86% of the session's output).
The stale-intent guard the old "reconcile ALL items every write" mandate provided is now *deferred, not preserved unchanged*: a stale sibling claim whose falsifier isn't a one-liner already in hand can survive this write and — if the session then crashes before another impag run — persist in `project_state.md` until the next Step 1 resume reconciles it (at a *small* prefix).
That later, narrower window is the accepted cost of not re-deriving every live claim at the heavy wrap-up prefix; the gap is bounded by the next impag invocation, whose **step 1 resume read IS that sweep** — the body says so explicitly, because the cap was for a while read as "old items are simply never revisited" and the pointer grew a per-plan ▶ log (crash-dash, 13.2 KB / 8 ▶ items, 2026-07-25).
**The cap never covered deletions.** A non-advanced item still loses its delete-class content (shipped recap, doc-recorded evidence, surplus ▶) at every write — that needs no falsifier and no recon, so it costs no wrap-up reasoning.
Same reasoning-economy motive behind the 2026-07-12 delegation-gate rewrite: on the crash-dash evening sessions, output was thinking-dominated (prose only 2.4%), so the lever is shrinking ceremony that gets re-reasoned each turn, not shortening prose.

**"Next action" pointer (why the body rewrites stale prose).** A pointer left describing an earlier stage misleads the resume target and can trip `impag-chain`'s paraphrase diagnostic — so each write rewrites it.
(Default target = most-recent plan in `docs/plans/`; a pointer to a *different* plan overrides, step 1 honors it.)

**Sentinel verification.** The driver consumes it after each detection — which is why the body re-emits it on every chaining stage; paraphrase or markdown formatting breaks unattended chained runs.
The verification grep — path AND regex — has ONE home: body §project_state. Don't restate it here (the two copies drifted apart until 2026-07-25: this file matched the legacy `: N` form, the body didn't, and both pointed at a project-relative path that never resolves). A project-relative `memory/project_state.md` never resolves, so a check against it can never ESTABLISH.

**Linked projects.** There the slug dir is a symlink into `<repo>/.claude/memory/`, made by `dotfiles/scripts/link-memory.sh`; the path skills use is unchanged, and git carries the files.
**"Chain ARMED" in the wrap-up prose is a CLAIM — run that grep before writing it.** A 2026-07-18 Stage-0 wrap-up asserted "Chain ARMED (sentinel at the file's end)" into a file holding zero sentinel lines. Same class as plan-hygiene's "a recorded SHA is a claim", but strictly worse to detect: a false SHA fails loudly at the next `git show`, whereas an absent sentinel fails as *nothing happens* — no error, no re-fire, and the next session reads the prose and believes the chain is live. Emit the sentinel and grep it in the **same burst** as the prose that claims it.
**User-decision carve-out rationale:** auto-firing into a blocked decision loops uselessly or steamrolls the deferral (operative rule at step 7).

---

## Step 1 — plan-authoring pass (conditional detail)

Body carries the full (a)(b)(c) sequence (Explore recon → `Plan` authors → write/commit/arm/STOP); this section holds only the detail that matters *while* authoring:

- **Arch-doc consult (a):** the stable-architecture doc (`docs/architecture-overview.md` / `ARCHITECTURE.md`) holds only system-specific AND durable design invariants — never a lessons ledger. Read it first, then brief the `Explore` agents to grep only for facts it lacks or that look stale, not to re-derive the whole subsystem.
- **`Plan` dispatch (b):** run it at its pinned frontmatter default. The Refactor-first assessment asks: should a refactor precede the feature, at what depth — 2-3 alternatives with `file:line` evidence (contract → `architecture-assessment-gate.md` §Refactor-first assessment — output contract).
- **Back-link rationale (vague rung):** the `→ plan: docs/plans/<name>.md` edit is the rung's contract both ways — it stops the next session (or `--all`'s sequencer) re-authoring a plan that already exists, and on a later load the rung belongs to the sub-plan.
- **Why STOP after authoring:** execution in the same session would run at plan-authoring's inflated prefix; the chained session starts fresh and re-reads the plan from disk (the durable contract).

## Step 9 — feedback graduation stays retro-owned

Feedback graduation (`memory-system.md §Graduation routing`) stays retro-owned (not in the body bullet) because it's coupled to retro Step 2's capture — graduating a steer wants the "why did this steer arise" context,
and its "surviving two retros → force the decision" can need a user decision impag's full-auto contract can't make.

---

## Step 1 — never measure a file (rationale)

Why the no-size-gate rule is absolute: **no file anywhere has a size cap** (`memory-system.md §No size caps`), so a `wc -c` on a doc or instruction file can only manufacture work the plan didn't ask for.
Skills, rules, references and CLAUDE.md all just get written to.
Trimming a file the plan **does** name is the work, not a violation — `/de-bloat` emits exactly such plans; unplanned condensing is a manual, user-run pass, not something an execution run drifts into.
Auto-memory is the one carve-out from *never-touch*: `project_state.md` / `roadmap.md` / `MEMORY.md` are content-pruned by their writer at the write (drop the delete classes, never measure) — mechanics in body §project_state.
A file that merely *looks* bloated becomes a `roadmap.md` NTH, never a pointer line: the pointer is read by every later session, so parking a cosmetic observation there re-bills it indefinitely.

## Step 2 — one rule, any task count (history)

The rule replaced a ≤4 / 5+ task-count split which stated the same thing twice and left "5+ without a dependency chain" unhandled. Nothing about the count changes the procedure: execute straight through in plan order and let the wrap-up limit (body step 4f) pick the stopping point at the most recent clean stage boundary.

## Step 3 — the five legitimate stops (rationale)

Body step 3 enumerates them and the list is closed, because every *other* stop shape is the recon → bank-notes → hand-off-to-a-fresh-session pattern wearing a plausible cost argument.
Banking notes instead of writing code pays the recon bill twice: once in the session that read the subsystem, once in the session that reads it again to act — and the first payment sits in the parent's prefix, re-billed as `cache_read` for the rest of that session.
So an executable code plan that ends with zero committed file edits is a **defect**, not a token-saving handoff.
(A plan-complete / no-open-work terminal report — body step 1 — is outside this frame, not a sixth stop. The `"eyeball"` carve-out is literal: the user's launch prompt must contain the word.)

**Delta-handoff (why an exhausted design-only subagent is a success).** A dispatch sized to one committable slice can still run out before coding; a precise delta-handoff re-fed to a fresh executor costs one brief, whereas re-reconning in the parent puts the whole subsystem into the prefix that survives the rest of the run.

## Step 4 — the measured-claim check (rationale)

Body step 4c dispatches a claim-check before committing a task whose deliverable is *prose about a number*. Why the normal instruments cannot cover it:
`tsc` and the test suite validate the code *around* a docblock table, a plan finding or a commit-message measurement, and pass the claim through unchecked — so the whole class defers to the step-6 review by construction, and a rung ships its correction one rung late.
Re-reading it yourself does not close the gap: the context that wrote the sentence from the probe output is the context that cannot see that the sentence names the wrong quantity — the same rationalization-inheritance that already forces review into a fresh sub-agent — and **a path-gated evidence rule loaded into the AUTHORING context does not substitute for a fresh reader.**
Hence the checker holds ONLY (i) the probe's raw output and (ii) the authored prose, never the plan, the intent, or the rung's narrative.
This is the one per-task dispatch that is **not** a budget regression: it replaces a step-6 finding that otherwise re-opens the same file a rung later.

**Why 4b's diff-skim is dispatch-only.** A filename-scope check can't catch a wrong-but-in-scope edit, and a subagent report that didn't name the behavior its tests asserted leaves that gap open. A direct edit has no such gap — the orchestrator wrote the lines.

## Step 4f — the ~45-turn session boundary (evidence)

Measured 2026-08-09 over 102 sessions (crash-dash session-token audit §I8):
the **median session is 68 turns**; impag sessions average **83** (qimpag 89) against **55** for sessions that load no skill; **62% of all token volume sits past turn 40**, and a turn at position 90 costs **2.3×** a turn at position 10.
The 3,395 turns past position 40 cost 433.6M tokens; re-run at the 21–40 band rate (~88k/turn) they cost 299M — a **~134M ≈ 19%** saving — and at the 1–20 rate (62k), 210M, a **32%** ceiling. The extra ~85 session starts cost ~51k of cold prefix each ≈ 4.3M, i.e. 3% of the saving.

**Why it is a step and not a Rules bullet.** Round 1 shipped the same boundary as a global `CLAUDE.md` §Interaction Style advisory ("a per-item decision loop triages ~8 items or ~40 turns, then writes the remainder back to the plan file and ends the session"). It did not bind: the sessions that overran it were specifically the ones running a skill whose own `## Process` told them to drive a plan to completion — **prose in file A lost to prose in file B**.
The mechanism already existed (the plan file is the handoff state — `skills/impag/SKILL.md` step 4f); only the trigger was missing, so the trigger moved into the binding step sequence at 4f, beside the budget check, and the `CLAUDE.md` paragraph shrank to a pointer in the same burst (one in, one out — `~/.claude/rules/claude-md-edits.md`).

## Step 8 — archiving is mechanical (rationale)

Why body step 8a forbids surfacing the archive as a question, an offer, or a tier-2 `Needs you:` line: it is mechanical, reversible and cite-safe, so surfacing it as a choice costs the user a whole session for a decision with one answer.
The same logic bans a `▶ Archive the plan doc` note in `project_state.md` — a deferred archive re-bills as pseudo-active work in *every* later session until someone does it.
The shape that silently rots is the plan that closed **without shipping** (refuted, abandoned, measured-dead): it has zero commits, so the "all stages committed" test never fires and the doc sits live forever.

**Tier discipline (8b).** The three tiers exist because a wrap-up that re-narrates per task duplicates the commit log at the session's most expensive prefix. Tier 2 is the only user-aimed surface, so its admission test is deliberately hostile — omitting every line but the push is the common correct outcome, and the push itself is never mirrored into memory because `git status -sb` is the cheaper source.

## Step 9 — the retro marker's admission test (rationale)

Why an item that cannot be stated in one sentence *with its destination doc named* is **dropped, not parked**: parking launders a candidate you failed to screen into a debt that the next session discharges by authoring prose, which is how a taxonomy grows classes nobody would have minted at a small prefix (`~/.claude/rules/instruction-file-discipline.md` §Write-time checks — a draft needing more than the target layer's shape is at the wrong layer).
A deferred payload re-bills in an always-loaded file **and** still costs a `/retro`, so prefer writing the one-liner to its home in the wrap-up burst and setting no marker at all; the marker exists only when even that single write is past budget.
Capture-gating rationale: a lesson qualifies only if a future session would repeat the mistake without it — a one-off, something the code or a test now enforces, and a restatement of an existing rule all fail that, which is why ZERO items is the normal outcome.

## Rules — thin orchestrator + late-session recon (rationale)

**Thin orchestrator.** Past the step-4f zone with stages still queued, every file body the orchestrator holds is re-billed on every remaining call of the longest part of the run — that is delegation gate (e) at its limit. Below that threshold the direct-edit default still wins (the subagent's re-read tax is not yet amortised → §Step 3 — delegate only when it pays).

**Late-session recon.** Recon whose only deliverable is a roadmap note or a pass/fail verdict buys a few hundred bytes and pays a subsystem's worth of prefix — the 2026-07-02 measurement (§Steps 1/3 + Rules — token-efficiency levers) found 17.1k of post-commit recon behind a 488-byte note. A plan-contract needs a **brief**, not the subsystem; and design banked anyway belongs in the plan doc or its addendum, never as rationale in `project_state`, which admits only the doc's name.

## project_state — why the admission test re-applies on carry-forward

A merge re-emits every old line, and re-emitting a line IS writing it. Lines that only ever face an *entry* test decay into a permanent log — the carry-forward growth measured in §project_state — full mechanics, header and guardrail prose included.
The delete-class sweep needs no falsifier and no recon, so it costs no wrap-up reasoning — which is why the reconcile *cap* (advanced items + one-liner falsifiers already in hand) never covered deletions.

## project_state — the admission test's exclusion lists

Each of the three tests names what it EXCLUDES, and the exclusion is the operative half: (1) OPEN or OWED — shipped, ruled, measured and decided are out; (2) the next session is *wrong* without it — nice-to-know is out; (3) no cheaper source has it — a git command, the plan doc and the commit log are out, so **cite the command, never its output**.
The ≤200-char shape excludes `file.ts:LINE` cites, measured tables, review NTHs and why-we-chose-this: those belong to the plan doc or the commit message.

## Step 8b — the two tier admission tests

**Tier 2 (`Needs you:`).** A line is admitted only if all three hold: a user-aimed verb (Push/Decide/Approve/Choose/Run); you can name what breaks if ignored; nothing future-dated. Each line may carry ≤1 clause naming what it unblocks, and nothing else — no rationale, evidence or file lists. Rejected: hedges, mere reports, discovered findings (those are tier 3).
**The mirror routing.** Any tier-2 line other than the push goes into memory the same turn — a do-next → project_state "Next action" **only when it is THE armed/in-flight item** (a do-next for any other plan joins the roadmap menu as one ▶); decisions and eyeball items → roadmap `§OWED[USER]`.
**Tier 3.** Each bullet names the outcome, not the edits — a per-change list is the defect. Durable gotchas may claim one bullet; anything else is dropped, not appended.

## Cloud session — push and foreground (rationale)

Why step 8 makes the push the session's own: there is no host to hand it to. Why 4d pushes after every commit: the container is reclaimed when the session idles out, so an unpushed commit is a lost commit; the session's own `claude/*` branch is the safety net, and step 8 lands it on the integration branch.

Why cloud executors run foreground: the launcher's own Stop hook (`~/.claude/stop-hook-git-check.sh`, wired from its `launcher-settings.json`, rewritten every session) blocks on uncommitted files each time the turn ends, and a backgrounded executor ends the turn exactly while its slice is uncommitted. The one-line answer works because the hook exits 0 on `stop_hook_active`, so the second stop passes; committing instead would put an unverified half-slice on `main`. It runs only when the session cwd is itself a git repo — a multi-repo session (cwd = the repos' parent) never sees it.

## Rules — per-stage plan files (rationale)

Why the test is a non-executing reader: an unconditional one-file-per-stage rule manufactures files by construction. Why never append to a growing design doc: later sessions re-read every prior stage.

## Step 7 — nice-to-have findings drop (rationale)

Why filing a nice-to-have is the default defect: you have already ruled it not worth doing, so its backlog entry's only drain (the commit that ships it) is the event that by construction never fires. "Would be nicer", "add a pin", "tighten this", "unreachable today" file nowhere.
