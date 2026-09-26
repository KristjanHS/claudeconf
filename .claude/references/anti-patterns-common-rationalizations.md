# Common Rationalizations & Process Anti-Patterns

Excuses people (and Claude) reach for when tempted to skip systematic debugging or design discipline. Loaded on demand via pointers from `systematic-debugging`, `mybrain`, and any other skill enforcing a process gate.

## Debugging Rationalizations

| Excuse | Reality |
|--------|---------|
| "Issue is simple, don't need process" | Simple issues have root causes too. Process is fast for simple bugs. |
| "Emergency, no time for process" | Systematic debugging is FASTER than guess-and-check thrashing. |
| "Just try this first, then investigate" | First fix sets the pattern. Do it right from the start. |
| "I'll write test after confirming fix works" | Untested fixes don't stick. Test first proves it. |
| "Multiple fixes at once saves time" | Can't isolate what worked. Causes new bugs. |
| "Reference too long, I'll adapt the pattern" | Partial understanding guarantees bugs. Read it completely. |
| "I see the problem, let me fix it" | Seeing symptoms ≠ understanding root cause. |
| "One more fix attempt" (after 2+ failures) | 3+ failures = architectural problem. Question pattern, don't fix again. |
| "Pre-existing noise, not from this change" | Tooling errors that survive across sessions are usually a 1-line config gap, not immutable. Investigate the resolver (pyrightconfig `extraPaths`, ruff target-version, etc.) before declaring it untouchable. |

## Persistence Anti-Pattern: storing the re-adjusted quantity instead of the invariant one

A feed that returns values **adjusted as of the fetch date** (dividend-adjusted closes, split-adjusted
prices, redenominated currency amounts) is not a stable fact about a date — it is a fact about
(date, fetch-date). Persist it as **levels** and two writers on different fetch dates disagree about the
same date; an `insert-missing` seed then freezes the seam **permanently** — it never self-heals, and a
deep backfill vs. a daily one-point write produce a series that is one vintage before the seed and
another after it. Ratio/return consumers that span the seam are the ones that break (cross-sectional
ranking especially). Single-window volatility looks immune and that is how the seam passes review — but
"immune" here holds only for a **one-shot seed** (the feed back-adjusts to the fetch's latest date, so a
single seed lands the seam at factor ≈1.0). A **re-run** `insert-missing` backfill leaves old rows on a
stale basis, and a measured worst leg at ~4%/yr drift moved a 20-day vol ratio 1.00 → 0.75 for ~20
trading days. Scope the immunity claim to the write pattern, not the consumer.
**Rule: persist the invariant quantity, not the re-adjusted one** — e.g. a chained ratio computed
*inside* one fetch's consistent vintage, or the raw unadjusted print plus the adjustment factors.

Paired review heuristic: **"both writers call the identical code path" is a claim about row SHAPE, not
row VALUE.** The same function fed a different input *vintage* still drifts. When a doc or docblock
asserts anti-drift from shared code, check what each caller **feeds** it, not just which function it
calls.

## Fail-Safe Anti-Pattern: an absent input reads as a calm input

A fail-safe (breaker, cash exit, de-risk latch) that gates on a **derived value** inherits every way that
value can shrink. When the derivation folds over N inputs and a fetch times out, the fold silently runs on
a **smaller denominator** — the missing input is dropped, not counted as its worst case — so the output
reads *calmer* than reality and the safety transition fires exactly when the system knows least. Live
instance: a budget-exhausted fetch walked `private-app`'s R4 breaker OUT of cash on one close by reading
`dial.targetRung` with no liveness guard, while the design text said "a non-live pillar counts as LOW";
the resulting state then **persisted** (3 closes to re-arm), so a transient became durable.
**Rule: guard de-risking/EXIT transitions on the LIVENESS of the inputs that produced the value, not on
the value alone** — an absent input is not a calm input. Fixed by threading a `pillarsLive` predicate
(`src/r4.ts`, `src/t1dial.ts`) into every exit condition, including the ratchet path.

Two asymmetries make this hard to catch: (a) ENTRY into safety is naturally conservative, so only the EXIT
side carries the bug — reviewing "does it de-risk correctly?" misses it; (b) the guard is invisible on a
fully-live close (the predicate is true, no cut moved), so every normal test passes. Test it by
constructing a starved input explicitly, and pair with the guard-on-INPUT-vs-OUTPUT lens below.

## Verification Anti-Pattern: the claim that cannot fail, shipped as coverage

A check that is *incapable* of returning a negative result reads to every later session as proof, and
nothing ever contradicts it. Shapes below, all shipped in 2026-07-18/19 private-app stages:

- **A fixture whose values are all EQUAL, pinning per-id wiring.** Every test seeding both sides of a
  pair with the same number (private-app `SB_STRAT`/`SB_BENCH` priors, both 100) makes a transposition
  algebraically invisible: swapping which id feeds which chain left the whole 4512-test suite green.
  A guard over *which id maps to which consumer* needs DISTINCT fixture values (100/200 → 110/240) or it
  asserts nothing about the mapping. Applies to any symmetric fixture — two legs, two columns, two feeds.

- **An asserted magnitude bound nobody evaluated.** A docblock said "largely immune, bounded by ~4%/yr"
  — the bound was the stated *reason* the design was safe, and computing it refuted the verdict.
  **Rule: if prose names a magnitude as the reason something is safe, evaluate that magnitude before
  shipping the verdict.** An un-evaluated bound is a hypothesis wearing a number.
- **A vacuous falsifier.** `grep -rn computeR5 supabase/migrations/` greps a TypeScript symbol in `.sql`
  files: it returns zero for *every* possible state of the repo. Likewise a single-file grep standing in
  for an import-graph property — reachability is transitive, one file is not.
  **Rule: a falsifier owes a demonstration that it CAN return non-zero.** Before recording one, run it
  against a state where the claim is false (or invert it and confirm the inversion hits). If you can't
  construct that state cheaply, the check is decoration — say so instead of recording it.
- **A red demo whose MUTATION silently no-opped.** The demo's second half is checked (does it go red?) and
  its first half is not (did the edit land?). A `str.replace()` in a throwaway script returns the string
  unchanged on no match, and `sed` exits 0 having matched nothing — so the suite stays green and reads as
  *the assertion is vacuous*, when in truth the assertion was never exercised. Seen 2026-09-10 authoring
  `make brief`'s falsifier: a Python heredoc replace failed on escaping, the rerun printed
  `Tests 6 passed`, and the honest reading was indistinguishable from a real vacuity finding.
  **Rule: assert the mutation landed before reading the result** — `assert old in s` in the script, or
  re-grep the mutated line and show it. A green run after an unverified mutation establishes nothing in
  either direction.
- **A gate read through a pipe reports the PIPE's exit code, not the gate's.** `cmd | tail -5` exits with
  `tail`'s status, so a failing gate renders as a pass and the transcript shows plausible output above it.
  **Rule: never judge pass/fail from a piped invocation** — run the gate bare, or `set -o pipefail`, or read
  `${PIPESTATUS[0]}`, and quote the exit code you actually observed.
  **Same defect, no pipe: `report "$(cmd)"`.** Command substitution discards the producer's status too, so
  an `awk`/`python` that CRASHED substitutes an empty string and the wrapper prints its `ok` branch over
  silence. Capture into a variable, test `$?` (or `set -e`), and treat empty output as a failure, not a pass.
  Two cheap recognition cues for the same shape: (a) **the check's subject is not in the diff** — a
  `grep -c <symbol> <file>` cited as a no-fork proof over a range that never touches `<file>` cannot
  register the change, and the fork it rules out would have landed elsewhere anyway; (b) **the fixture
  lacks the structure that triggers the bug** — a regression pin built on 900 *consecutive calendar days*
  was designated to catch weekend-gap arithmetic over a *trading-day* series, so it could not observe it.
  Check that the diff's subject and the fixture's structure both intersect the claim.
- **A de-duplication's pin that is vacuous BY CONSTRUCTION.** Consolidating two hand-typed literals into
  one exported const makes `expect(siteA).toEqual(siteB)` compare two expressions that now resolve to the
  same object — it passes for every possible value and can never observe drift again.
  **Rule: a pin guarding a single-source claim needs a deliberate THIRD hand-written literal** (the
  expected shape, spelled out) so there is something the const can disagree with. Recognition cue: after a
  de-dup, the test's two operands trace back to the same definition.
  Sibling cue for the *edit* that motivated it: **a fix that closes one drift seam is free to open
  another** — a change justified as "one caller shape, nothing to drift" can hand-type a second copy of the
  very value it centralized, in the same commit. Grep the consolidated shape file-wide before claiming the
  seam is closed.
- **A check whose REFERENCE DATA degrades silently to empty.** Distinct from the vacuous falsifier
  above: this check *can* fail in principle, but it classifies subjects against a fetched reference, and
  the fetcher swallows its errors. `fetchVixSeries` returns `[]` on non-200/timeout/429/parse-failure
  (it warns, never throws), so an audit comparing stored rows to it bucketed *every* row "unverifiable",
  counted zero disagreements, and printed a confident ✅ — **a green reachable by feed loss alone**,
  byte-identical to a real pass. **Rule: when a check's verdict depends on fetched reference data, assert
  the reference is non-empty and fail loud when it isn't** — "nothing disagreed" is not "nothing is
  wrong". Recognition cue: an *unverifiable/skipped* bucket that grows on the same error the check exists
  to detect. Demo the guard by mutating the fetcher to return empty.
- **An unverified sweep claim in a COMMIT MESSAGE.** "swept …, none found" was written after a one-site
  fix; a sibling twelve lines away carried the same defect. A commit message is the most durable home
  for this failure — later plans are authored from commit archaeology, so a false sweep there seeds work
  that skips the real sites, and unlike prose nobody re-reads it against the code. **Rule: never write
  "swept" / "none remain" / "file-wide" in a commit message without pasting the sweep command into the
  same message — and having run it file-wide, comments and the symbol's own DEFINITION SITE excluded (else
  the grep indicts the very code/prose documenting the change it polices).**
  Corollary on *what* to sweep: **when the defect is a mis-dating / mis-labelling, grep every RENDERER of
  the value, not just its writer.** A 2026-07-19 fix corrected the persistence path (`tracks.ts` stamped
  the run's `asOf` onto a feed point dated earlier); review then found the identical mis-dating on the
  notify path (`bottom_tier.ts` captioned the push "as of <asOf>" over a week-old close). A sweep scoped
  to writers reads as file-wide and isn't.
- **A guard asserting on the INPUT that differs, not the OUTPUT whose sameness is the failure.** An A/B
  probe's anti-collapse guard compared the two arms' *cut values*; the arms are *state arrays*. Equal
  cuts are sufficient for A/A but not necessary, so the guard could not fire on the collapse it was
  written for — and the governing rule already said "throw when the arms agree day-for-day."
  **Rule: assert on the artifact whose sameness IS the failure mode, never a knob that merely correlates
  with it.** When a guard and its rule disagree about what to compare, the rule is right. Upstream of the
  guard: before attributing an observed A/B difference to the mechanism under test, equalise every parameter
  it does NOT control — an uncontrolled confounder makes the difference unattributable.
- **A falsifier that RECOMPUTES the value it claims to pin.** `npm run probe:bund` re-derived BUND's cuts
  from live data and printed them, and was recorded as the check for the *shipped* cut constants — but it
  never read those constants, so its output was identical whether or not the shipped pair matched. The
  constants were pinned by nothing and the "re-run confirms" was an A/A; only code review caught it.
  **Rule: a falsifier for a shipped VALUE must read the shipped artifact** — grep the constant where it is
  defined, or have the probe import it and assert equality. A recomputation is a second opinion, not a pin.

- **A hand-copied MIRROR of a source-of-truth list, with a comment calling itself a drift tripwire.** A
  `.js` test re-typed a TS union's four members and its comment claimed "a reason added there without a
  note here goes red." It could not: nothing linked the array to the union, so a fifth member left the
  array at four, every test green, and the FE rendering nothing — the exact ambiguity the feature removed.
  The guard covered only the direction it was written from. **Rule: a tripwire over a source-of-truth list
  must IMPORT that list, not restate it** — and when the languages differ, that import is the whole point
  of the test. Corollary on the can-it-fail demo: **inject the drift the tripwire CLAIMS to catch** (add a
  member upstream), never merely delete an entry it already maps — deleting proves the direction that was
  never in doubt.
  Worst case of this shape: **the mirror lives in a NON-EXECUTABLE file, so nothing can assert it.**
  `openapi.yaml`'s `posture`/`equityPct` enums mirrored a TS constant; the contract suite's
  `required`⟷keys parity check reads as covering the schema but is blind to enum *members*, so dropping a
  posture or typo'ing a weight left all 30 cases green — the headline edit of the stage shipped
  falsifier-free. **Rule: a hand-typed list in a spec/config file needs a test that IMPORTS the executable
  constant and asserts the file's contents against it**; structural checks over such files (key parity,
  schema-valid) never reach values. Inverse shape — a *generated* artifact (committed generator output, no
  build step) silently desyncs from its emitter with nothing in CI: assert freshness at its READ site against
  the raw input, since only a zero-churn regen at the artifact's own epoch can falsify "it's current".

- **A fixture that cannot LAND on the boundary it claims to pin.** A boundary test passed under *both*
  directions of the `>=`-vs-`>` comparison it existed to fix: ranks are `k / windowSize`, so the cut is
  observable only where it is exactly representable, and at window 254 the 0.60 cut sits at `152.4` —
  no `k` lands on it. The mutation demo "passed" because the mutated branch was unreachable from the
  fixture, which reads identically to a real pin. **Rule: a mutation demo proves nothing unless the
  fixture can REACH the mutated branch** — for a quantized/derived threshold, check the arithmetic makes
  the boundary exactly representable (here: a 255-wide window, divisible by 5, puts `k=153` exactly on
  0.60). Recognition cue: the guarded value is a ratio/quantile/index over a window whose size you chose
  for unrelated reasons.
- **A red demo that goes red BEFORE reaching the line it claims to guard.** The inverse of the above: the
  mutation *does* turn the suite red, so it reads as a passing demo — but the file died at **collection**, not
  at the assertion. A fixture builder called at MODULE TOP LEVEL (`const v = buildVintage()`) plus a throwing
  input guard means the mutated line is never evaluated; the docblock then asserts a demonstration that never
  happened. **Rule: a red demo owes proof that the red came FROM the guarded line** — confirm the failure names
  that test/assertion, not a collection or import error. Recognition cue: the mutation targets a validator,
  constructor or schema guard, and the fixture is built once at module scope. Fix: move the builder inside the
  test body (or `beforeEach`) so a throw is scoped to one case.
- **A fabricated timestamp, with no degrade trace.** Writing the run's `asOf` onto a datum the feed dated
  earlier persists a silently wrong row: nothing throws, no staleness entry is emitted, and downstream
  deltas drift permanently. **Rule: persist the datum's OWN date and reserve the degrade path for genuine
  staleness** — a fabricated date is a data-quality bug that no falsifier downstream can see, because
  every consumer trusts the column.
- **A grep written into a docblock but never RUN on the clean tree.** Distinct from the vacuous falsifier:
  these greps *could* fail — and two of them were already RED at the moment they shipped, inside the very
  2026-07-19 pass that existed to delete false claims. The expectation (`→ 1`, `→ 0`) was reasoned out
  from the code rather than executed, so the docblock became a second false claim wearing a command.
  A recorded falsifier is read by later sessions as *already verified*; nobody re-runs it. **Rule: paste a
  falsifier only after running it on the clean tree and copying its ACTUAL output** — reasoned-out
  expectations are hypotheses, and a check-authoring pass is exactly where the failure hides, because
  attention is on the claims being fixed, not on the checks being added.
- **A falsifier the PLAN authored, inherited by the executor as already-validated.** Every shape above
  assumes you wrote the check; this one arrives pre-written and carries a plan's authority. W5-b Stage
  1.2's plan-stated demo ("shrink the slice, confirm red") goes red from the *starved rank window* and
  fires identically with the latch removed from the code — it could not observe the thing the stage
  shipped. Structurally no slice could: scan depth ≤ `sliceLen − ARM_MIN_OBS`, so truncating the walk
  needs a slice smaller than the rank window it also starves. **Rule: a plan-supplied falsifier is a
  hypothesis, not a validated check — run its can-it-fail demo at EXECUTION time, against the code with
  the new behavior removed.** Corollary: when the property is a *latch* (state carried across steps), an
  equivalence test can never see it — both sides run the latch. Pin it directly (count the days the
  latch alone holds the state) instead.
- **A stage-boundary claim authored as REASSURANCE, and therefore never run.** A plan promised "the API/FE
  still typecheck because `equityPct` is additive" — but the field was declared `required`, which breaks
  every existing literal at compile time, and the new enum member moved runtime expectations in three
  suites. The stage could not be green alone. The tell is rhetorical: the sentence exists to say *don't
  worry*, so nobody treats it as a prediction with a command attached. **Rule: a plan's "this still
  compiles / nothing else changes" line is an untested hypothesis — run the build at that boundary before
  believing it, and re-check every LATER stage's boundary line in the same plan** (one un-run boundary
  claim means the author was reasoning, not executing, throughout). Recognition cue: **"additive" applied
  to a `required` field, a new enum member, or a widened union** — none of those are additive to consumers.
- **An assertion whose operands are ALL module constants.** `expect(N - ARM_MIN_OBS > ARM_RANGE_WINDOW / 2)`
  — three constants, zero fixture-derived operands: it restates arithmetic the compiler already knows and
  is green for every possible fixture. This shipped **three hours after** the "run your falsifier before
  shipping it" rule above was graduated into this file, in the same session. The gap was scope: the
  mutation demo ran on the *slice* (the thing under active thought) and never on *the assertion line
  itself*. **Rule: writing the rule does not install the habit — before committing, grep the diff's new
  `expect(` lines and reject any whose operands are all constants**; then mutate the exact line each new
  assertion guards, not the fixture around it, and confirm red.
- **A check whose OUTPUT FORMAT varies by CALLER IDENTITY.** A verifier that renders one way for a human and
  another for an agent can pass for one reader and lie to the other — the same run, two verdicts. **Rule: the
  verdict an agent acts on must be the same machine-readable result regardless of who invoked the check** —
  format-by-caller is an unfalsifiable green for whichever caller sees the softer view.
- **A comparison whose BASELINE cannot produce the outcome you measure — RED-vs-RED.** A lead-time / false-
  positive validation that pits a candidate signal against a "slow baseline" is vacuous if the baseline is
  itself incapable of the RED (danger) state — every window is RED-vs-RED, so the candidate can neither lead
  nor false-positive relative to it, and the run reads as passing coverage. **Rule: before picking a control
  baseline, confirm it is CAPABLE of the outcome you compare against** — check its `.derived.red` / the
  scorer's red-branch is reachable for the population under test. A control that can only produce one label
  measures nothing (private-app 2026-07-22: a slow baseline picked for a lead/FP check had no live red-branch).
  **Same shape one axis over: the ANCHOR, not the baseline, can be incapable of showing the effect** — and a
  single-anchor before/after then reads as a property of the system. private-app 2026-08-08: a re-horizon's
  before/after was drawn at *one* close, chosen as "the latest where the two arms differ", and the ordering
  came out identical — written up as "absorbed by the fold". That close was the **saturated** one (every leg
  already at the ceiling), the single configuration in which no one member's move can propagate; sweeping all
  418 separating closes showed the ladder moving on 228, and the user-visible held sleeve on 33.
  **Rule: an n=1 comparison licenses a claim about that anchor and nothing more — sweep the population
  before stating a property, and pick any illustrative anchor by whether the effect CAN show there**
  (not saturated, not floored, not clamped). Recognition cue: the write-up says "identical" / "no change"
  from one date, or the anchor was picked by a criterion unrelated to observability.
  **Same trap when REDUCING a permutation table to plan-named cells:** a surviving cell can sit on the
  saturated configuration and pass forever — before cutting the table, mutate each keeper's guarded line
  and confirm it fails INDEPENDENTLY of its siblings (private-app 2026-09-01).

- **A guard's red demo needs a STUB, never the live command.** The mutate-and-confirm-red duty says prove
  the guard *can* fire — it never says invoke the thing the guard protects. A subagent told "do not run
  `make prodcron`" ran exactly that to demonstrate its new guard, in a tree where the guard passes, so the
  real prod cron fired (private-app 2026-08-06). The rationalization is *"the demo has to be real or it
  proves nothing"* — false: what must be real is the **guard's input**, so stub the side-effecting call and
  feed the guard the state that trips it. **Any red demo whose failure path executes an irreversible or
  outward-facing action is mis-designed** — refactor until the guard is reachable without it, and say so
  rather than reaching for the live command. Binds subagent briefs too: a dispatch that carries the red-demo
  clause and a "don't touch prod" constraint must state which stub discharges the first without breaking the
  second, or the subagent resolves the conflict in favour of realism.

- **An ALLOWANCE / whitelist row admitted on an UNMEASURED cause.** An entry that exempts a subject from a
  falsifier carries an implicit CAUSE claim ("this row is benign *because* <mechanism>"), and admitting it
  turns the check green over the exact defect the check exists to catch — permanently, since nobody
  re-audits an exemption. private-app 2026-08-08: stale CG rows were exempted on a "base-feed skew" story
  that was plausible, was written into both the code and the plan, and was refuted by ONE direct
  measurement (the skew moves the cut the *opposite* direction; the rows were simply stale, and a
  `--restate` fixed them). **Rule: an exemption is a measurement, not a judgement — before adding an
  allowance entry, rescore the subject through the PRODUCTION path and confirm the named mechanism is what
  produces the anomaly.** If it is not, you have a bug, not an exception. Recognition cue: the allowance's
  comment explains *why* the row is unfixable, and that explanation was reasoned rather than run.

All of these generalize: **coverage is the set of ways a claim could have died, not the set of checks
attached to it.** Count the former. Note several were caught by *reading the comment against the code*,
not the code alone — prose asserting a guarantee is itself a claim to falsify (the `tracks.ts` docblock
asserted "the live tail and the seeded history can't drift" while `delta20` was drifting).

- **A before/after read through two different filters is not a measurement.** Comparing a `tail -30` of one
  run against a `grep` of the other made a still-present warning look eliminated — the reworded line was
  simply never in view. Both sides of a claimed delta run the SAME extraction, or the delta is an artifact
  of the viewport.

- **A mutation that moves the assertion AND its expectation together.** When a test reads both the
  asserted value and the expected value from the same source (a fixture JSON both sides load), editing
  that source re-points both halves and the test stays green — the demo proves the test is *consistent*,
  never that it *guards*. **Rule: mutate the PRODUCING side** (the code that derives the value), not the
  shared input both sides read.

- **A consumer map built by reading the DIFF instead of grepping the SYMBOL.** The diff shows where the
  change landed, not where the name is read, so the map silently omits every pre-existing consumer —
  including the one that moves behaviour. ai-coding-journey 2026-09-18: a commit claimed to enumerate the
  `ABSENT` consumers named 2 of 6, missing the build-moving one. **Rule: a "who consumes X" claim is a
  grep for X over the whole tree, never a re-read of the change that introduced it.**

- **A file-wide grep for a defect class cannot catch the instance the same commit writes.** The sweep
  runs against the tree as it was reasoned about, and the line just authored is not a suspect — it is
  the fix. ai-coding-journey 2026-09-19: the commit that removed three false "this form is absent"
  claims and grepped `scripts/deck/` for the rest *introduced a fourth*, a census header reading
  "ABSENT by design (no derived source)" printed directly above the derived candidate's count of 1.
  **Rule: run the class grep over the DIFF's own added lines as well as the tree, or have a second
  reader run it — an author's sweep structurally excludes the author's new text.**

- **A mutation too WEAK to move the asserted substring.** The check may be sound and the demo still
  vacuous: ai-coding-journey 2026-09-19, unscoping `merge_slice_row`'s scan while leaving `head + sep`
  intact kept the original row inside `head`, so a `toContain` assertion stayed green against a genuinely
  broken merge. **Rule: a red demo must delete or corrupt the exact bytes the assertion reads — if the
  asserted string can survive the mutation through any other path, the demo proved nothing.**

## Staleness Anti-Pattern: correcting a stale claim instead of deleting it

*"I'll note at the top that these are now closed — deleting might lose something."*

A living state file (memory pointer, runbook, status doc) accumulates claims that were true when written.
When one goes stale, the cheap move is to **add a correction above it** rather than delete the line. This
feels conservative and is the opposite: the file now asserts both the claim and its refutation, and a reader
who greps — or who starts below the correction — finds the claim alone. A 2026-07-20 `project_state.md` had
grown a header reading *"everything below that says 'NOT pushed' is CLOSED"* above **six** surviving
"NOT pushed" lines; by then the header itself was stale too.

Two rules:
- **Delete the stale line in the same edit that discovers it.** A correction is only warranted when the
  *reason* the claim was wrong is itself load-bearing — and then it replaces the claim, never stacks on it.
- **Don't record state a cheap command already answers.** Uncommitted-file lists, push status, local-commit
  counts, SHA recaps, test tallies: a doc cannot observe the working tree, so these are *guaranteed* to rot
  and there is nothing to preserve. Cite the command (`git log --oneline origin/main..HEAD`), not its output.
  This is the durable fix — a class of line that can't go stale needs no correction discipline at all.

Recognition cue: the file contains a sentence about *other sentences in the same file*.

## Design Anti-Pattern: "This Is Too Simple To Need A Design"

Every project goes through the design process. A config change, a one-page proposal, a simple script — all of them. "Simple" projects are where unexamined assumptions cause the most wasted work. The design can be short (a few sentences for truly simple projects), but present it and get approval.

## Stopping-Rule Anti-Pattern: running a stage that cannot flip the verdict

Pre-register an experiment's stopping point alongside its decision rule; once the rule resolves, any further arm or stage that cannot change the verdict is pure spend rationalized as rigor ("for fidelity", "for completeness"). Incident 2026-07-09 (review-gate bench): re-running a reconstructed pipeline's verify stage after both arms had already answered cost 218k tokens and changed nothing.

## Duplication Anti-Pattern: guarding mirrors where an import is reachable

Faced with the same value copied across files, the reflex is a **guard** — a test asserting the copies agree. It feels equivalent to single-sourcing and is cheaper to write, which is the rationalization: *"the guard pins it, so the duplication is safe."*

It is not equivalent, and the asymmetry is one-directional: **a guard can only pin what you already knew to enumerate.** Its coverage is a hand-written list, so every mirror you failed to notice stays unguarded *and* silently reads as covered — the guard's green is evidence about the list, not about the codebase. An **import** has no list: it makes the drift unrepresentable for every consumer, including the ones you never found.

Rule: **when an import is reachable, single-source — do not guard.** Reserve guards for cases where an import genuinely is not reachable (a cycle, a build boundary, a non-TS surface like `.sql`/`.yaml`/generated output), and say which one applies.

Incident 2026-07-24 (private-app name-duplication sweep): converting mirrored names to imports immediately surfaced **2 live drifts the preceding enumeration sweep had not listed** (`complacency-duration.series`, F5 `derived.label`). Both would have survived a mirror-guard indefinitely, because a guard over an enumerated set cannot fail on a member absent from that set.

Recognition cue: you are about to write a test whose assertion is "these N copies are equal", and nothing stops file A from importing the constant out of file B. Also the phrase "we'll add a guard so they can't drift" — check whether *can't* means *unrepresentable* or merely *listed*.

## Scoping Anti-Pattern: an artifact's name is not its scope

Counting enforcement points by *artifact* over-counts what removing one costs, and under-counts what it breaks. Incident 2026-07-25: `docs-bloat-gate.py` read as "one budget gate" from its name, so an `AskUserQuestion` round offered "delete the hook" as a clean removal — but it carried **four** independent signals, only S1 of which was budget machinery; deleting it would have silently dropped three unrelated checks. A premise re-check caught it before execution.

Rule: before offering removal (or counting coverage) of a named artifact, **grep its body for distinct signals** and count those, not files. Recognition cue: a decision option whose description says "just the X gate" about a file you have not opened.

## Transplant Anti-Pattern: a convention adopted without its home problem

A literature/industry convention arrives well-sourced, and the citation count is taken as fit ("this is how it's done"). But a convention solves the problem it was BUILT for, and transplanted into a different problem it can undo the very fix in flight. Incident 2026-07-25 (private-app EW): the structural-zero convention — drop a cell that cannot occur from the fitted denominator — exists to remove *estimation bias in a fitted model*, not to make *differently-covered units comparable*; applied to the danger ledger it would have restored exactly the leg ordering the plan existed to correct. The convention that did transfer (roster rule, Conference Board / ECB CISS) matched the actual problem: applicability belongs in the definition of the measured set, not in a parked weight.

Rule: when research returns a convention, **state its home problem in one line and compare it to yours before recommending it** — and if they differ, derive the consequence numerically, showing the transplant's output value next to the current one. The arithmetic exposes the mismatch; the citation never does. Recognition cue: the argument for adopting is about the convention's pedigree rather than about your own problem's shape.

## Seam Anti-Pattern: patching the reader list instead of moving the attach point down a layer

A design says "X is the ONE seam — attach here." Recon then finds X has four readers, and the reflex is to extend the plan: attach at each of the four. That multiplies the invariant across sites, and every later reader has to keep them in sync. The claim was not wrong, it was stated at the wrong **layer**: 2026-08-04, the four readers of a weight table all consumed the same downstream state map, so moving the attach point one layer *down* restored a genuine single seam — and dissolved a separate review finding that only existed because of the multi-site patch.

Rule: when a single-seam claim collapses under recon, **look for the layer where it becomes true again** (what do all N readers have in common downstream?) before accepting an N-site design. Recognition cue: a plan step that grows from "edit here" to "edit here, here, here and here" while the invariant stays one sentence.

## Reporting Anti-Pattern: a probe's reading line authored as the finding it was built to display

A probe written to DISPLAY a prior finding invites authoring its reading/interpretation line AS that
finding — the narrative is already in hand, so the output text gets written before any output exists.
The probe then cannot contradict its own summary: whatever it computes, the line still reads as the
finding. Rule: **write the interpretation only after the first run**, off the numbers that came back —
and if the run refutes the premise, the reading line is the first thing to change. Recognition cue: a
`console.log` summary sentence committed in the same edit that created the measurement.

## Delegation Anti-Pattern: a partial result from an outside turn reads as a finished one

Bulk generation handed to an external turn (a claude.ai chat, a one-shot agent) comes back covering a
*fraction* of the set and looks complete — the reply is well-formed, so nothing in it announces the gap,
and the receiving repo has no expected count to compare against. A firmer instruction ("do ALL of them")
does not fix it: the next reply is a different fraction, equally well-formed.
**Rule: make the RECEIVING repo compute the denominator, and refuse on the shortfall.** Enumerate the
expected set from tracked data (a manifest), build the artifact from that manifest so an unauthored item
ships as a loud placeholder rather than a silently shorter output, and let the coverage check red.
Recognition cue: the acceptance criterion for a delegated batch is "the reply looks right", not a count
the repo can recompute without the reply.
