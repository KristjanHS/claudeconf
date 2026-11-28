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
prices, redenominated amounts) is a fact about (date, fetch-date), not about the date. Persist it as levels
and two writers on different fetch dates disagree about the same date; an `insert-missing` seed then
freezes that seam permanently, and ratio/return consumers spanning it break. A one-shot seed lands the seam
at factor ≈1.0, so it passes review; a re-run backfill leaves old rows on a stale basis (a measured ~4%/yr
drift moved a 20-day vol ratio 1.00 → 0.75). Scope any immunity claim to the write pattern, not the consumer.
**Rule: persist the invariant quantity, not the re-adjusted one** — a chained ratio computed inside one
fetch's consistent vintage, or the raw unadjusted print plus the adjustment factors.

Paired review heuristic: **"both writers call the identical code path" is a claim about row SHAPE, not
row VALUE.** Check what each caller **feeds** the shared function, not just which function it calls.

## Fail-Safe Anti-Pattern: an absent input reads as a calm input

A fail-safe (breaker, cash exit, de-risk latch) that gates on a **derived value** inherits every way that
value can shrink. When a fold over N inputs loses one to a timeout, it runs on a smaller denominator, so
the output reads *calmer* than reality and the safety transition fires exactly when the system knows least
— and a latched state turns the transient into a durable one.
**Rule: guard de-risking/EXIT transitions on the LIVENESS of the inputs that produced the value, not on
the value alone** — thread a liveness predicate into every exit condition, ratchet paths included.

Two asymmetries hide it: ENTRY into safety is naturally conservative, so only the EXIT side carries the
bug; and the guard is invisible on a fully-live run, so every normal test passes. Test it by constructing
a starved input explicitly.

## Verification Anti-Pattern: the claim that cannot fail, shipped as coverage

A check that is *incapable* of returning a negative result reads to every later session as proof, and
nothing ever contradicts it. The shapes:

- **A vacuous falsifier.** Grepping a TypeScript symbol in `.sql` files returns zero for every state of the
  repo; a single-file grep cannot stand in for a transitive import-graph property.
  **Rule: a falsifier owes a demonstration that it CAN return non-zero** — run it against a state where the
  claim is false (or invert it and confirm the inversion hits); for a test, on the narrowest suite slice that
  executes the guarded line. Can't build that state cheaply? Say the check
  is decoration instead of recording it.
- **A fixture whose values are all EQUAL, pinning per-id wiring.** Seeding both sides of a pair with the same
  number makes a transposition algebraically invisible. A mapping guard needs DISTINCT values (100/200).
- **An asserted magnitude bound nobody evaluated.** If prose names a magnitude as the reason something is
  safe, compute it before shipping the verdict — an un-evaluated bound is a hypothesis wearing a number.
- **A red demo whose MUTATION silently no-opped.** `str.replace()` returns the string unchanged on no match
  and `sed` exits 0 having matched nothing, so the suite stays green and reads as a vacuity finding.
  **Rule: assert the mutation landed before reading the result** (`assert old in s`, or re-grep the line).
- **A gate read through a pipe reports the PIPE's exit code.** `cmd | tail -5` exits with `tail`'s status;
  `report "$(cmd)"` discards the producer's status too. **Rule: never judge pass/fail from a piped or
  substituted invocation** — run it bare, use `set -o pipefail` / `${PIPESTATUS[0]}`, treat empty output as failure.
- **A check whose subject or fixture misses the claim.** A `grep -c <symbol> <file>` over a range that never
  touches `<file>` cannot register the change; a regression pin built on consecutive calendar days cannot
  observe trading-day gap arithmetic. Check that the diff's subject and the fixture's structure both
  intersect the claim.
- **A de-duplication's pin that is vacuous BY CONSTRUCTION.** After two literals become one const,
  `expect(siteA).toEqual(siteB)` compares the same object. **Rule: a single-source pin needs a THIRD
  hand-written literal** the const can disagree with. And grep file-wide: a fix that closes one drift seam
  can hand-type a second copy of the value it centralized.
- **A check whose REFERENCE DATA degrades silently to empty.** A fetcher that returns `[]` on error lets an
  audit bucket every row "unverifiable", count zero disagreements and print a green reachable by feed loss
  alone. **Rule: assert the reference is non-empty and fail loud when it isn't**; demo by stubbing it empty.
- **An unverified sweep claim in a COMMIT MESSAGE.** Later plans are authored from commit archaeology, so a
  false "swept, none found" seeds work that skips the real sites. **Rule: never write "swept" / "none
  remain" / "file-wide" without pasting the sweep command** — run file-wide, excluding comments and the
  symbol's own definition site. For a mis-dating or mis-labelling, grep every RENDERER of the value, not
  just its writer.
- **A guard asserting on the INPUT that differs, not the OUTPUT whose sameness is the failure.** An A/B
  anti-collapse guard compared the arms' cut values while the arms are state arrays, so it could not fire.
  **Rule: assert on the artifact whose sameness IS the failure mode**; when guard and rule disagree on what
  to compare, the rule is right. Equalise every parameter the mechanism does NOT control before attributing
  an A/B difference to it.
- **A falsifier that RECOMPUTES the value it claims to pin.** A probe re-deriving cut constants from live data
  never reads the shipped constants, so its output is identical either way. **Rule: a falsifier for a
  shipped VALUE must read the shipped artifact** — a recomputation is a second opinion, not a pin.
- **A hand-copied MIRROR of a source-of-truth list, calling itself a drift tripwire.** Nothing links the
  re-typed array to the union, so a new upstream member leaves every test green. **Rule: a tripwire over a
  source-of-truth list must IMPORT that list**; demo by injecting the drift it claims to catch (add a member
  upstream), not by deleting an entry. A mirror in a spec/config file (YAML enums) needs a test that imports
  the executable constant — key-parity and schema checks never reach values. A committed generated artifact
  needs a freshness assert at its read site.
- **A fixture that cannot LAND on the boundary it claims to pin.** Ranks are `k / windowSize`, so at window
  254 a 0.60 cut sits at 152.4 and both `>=` and `>` pass. **Rule: a mutation demo proves nothing unless the
  fixture can REACH the mutated branch** — make the boundary exactly representable (a 255-wide window puts
  `k=153` on 0.60).
- **A red demo that goes red BEFORE reaching the guarded line.** A fixture builder at module top level plus a
  throwing input guard dies at collection. **Rule: confirm the failure names the guarded test/assertion**,
  not a collection or import error; build fixtures inside the test body.
- **A fabricated timestamp, with no degrade trace.** Writing the run's `asOf` onto a datum the feed dated
  earlier persists a silently wrong row every consumer trusts. **Rule: persist the datum's OWN date** and
  reserve the degrade path for genuine staleness.
- **A grep written into a docblock but never RUN on the clean tree.** Reasoned-out expectations (`→ 1`,
  `→ 0`) ship already red and are read later as verified. **Rule: paste a falsifier only after running it
  on the clean tree and copying its ACTUAL output.**
- **A falsifier the PLAN authored, inherited as already-validated.** A plan-stated demo can go red from an
  unrelated starved input and fire identically with the feature removed. **Rule: run a plan-supplied
  falsifier's can-it-fail demo at EXECUTION time, against the code with the new behavior removed.** A latch
  (state carried across steps) is invisible to an equivalence test — pin it directly.
- **A stage-boundary claim authored as REASSURANCE.** "Still typechecks, the field is additive" was false
  for a `required` field. **Rule: run the build at every plan boundary line before believing it.** Cue:
  "additive" applied to a `required` field, a new enum member or a widened union.
- **An assertion whose operands are ALL module constants.** It restates compile-time arithmetic and is green
  for every fixture. **Rule: grep the diff's new `expect(` lines and reject all-constant ones**; then mutate
  the exact line each new assertion guards and confirm red.
- **A check whose OUTPUT FORMAT varies by CALLER IDENTITY.** **Rule: the verdict an agent acts on must be
  the same machine-readable result whoever invoked the check.**
- **A comparison whose BASELINE or ANCHOR cannot produce the outcome — RED-vs-RED.** A control baseline
  incapable of the RED state makes a lead/false-positive comparison vacuous; an anchor picked at a saturated
  configuration shows "identical" while a sweep shows the effect. **Rule: confirm the control CAN produce
  the outcome, and sweep the population before stating a property** — an n=1 comparison licenses a claim
  about that anchor only. When reducing a permutation table, confirm each keeper fails independently.
- **A guard's red demo needs a STUB, never the live command.** What must be real is the guard's INPUT;
  stub the side-effecting call. A red demo whose failure path runs an irreversible or outward-facing action
  is mis-designed. A brief carrying both a red-demo clause and "don't touch prod" must name the stub.
- **An ALLOWANCE / whitelist row admitted on an UNMEASURED cause.** An exemption turns the check green over
  the exact defect it exists to catch, permanently. **Rule: an exemption is a measurement** — rescore the
  subject through the PRODUCTION path and confirm the named mechanism produces the anomaly first.
- **A before/after read through two different filters.** Both sides of a claimed delta run the SAME
  extraction, or the delta is an artifact of the viewport.
- **A mutation that moves the assertion AND its expectation together.** When both sides load the same
  fixture, editing it proves consistency, not guarding. **Rule: mutate the PRODUCING side.**
- **A consumer map built by reading the DIFF instead of grepping the SYMBOL.** **Rule: a "who consumes X"
  claim is a grep for X over the whole tree**, never a re-read of the change that introduced it.
- **A file-wide grep for a defect class cannot catch the instance the same commit writes.** **Rule: run
  the class grep over the diff's added lines as well as the tree**, or have a second reader run it.
- **A mutation too WEAK to move the asserted substring.** **Rule: a red demo must delete or corrupt the
  exact bytes the assertion reads.**

All of these generalize: **coverage is the set of ways a claim could have died, not the set of checks
attached to it.** Prose asserting a guarantee is itself a claim to falsify — read the comment against the code.

## Staleness Anti-Pattern: correcting a stale claim instead of deleting it

*"I'll note at the top that these are now closed — deleting might lose something."*

Adding a correction above a stale line leaves the file asserting both the claim and its refutation; a
reader who greps, or starts below the correction, finds the claim alone.

- **Delete the stale line in the same edit that discovers it.** A correction is warranted only when the
  *reason* the claim was wrong is load-bearing — and then it replaces the claim, never stacks on it.
- **Don't record state a cheap command already answers** (uncommitted files, push status, SHA recaps, test
  tallies). Cite the command (`git log --oneline origin/main..HEAD`), not its output.

Recognition cue: the file contains a sentence about *other sentences in the same file*.

## Design Anti-Pattern: "This Is Too Simple To Need A Design"

Every project goes through the design process. A config change, a one-page proposal, a simple script — all of them. "Simple" projects are where unexamined assumptions cause the most wasted work. The design can be short (a few sentences for truly simple projects), but present it and get approval.

## Stopping-Rule Anti-Pattern: running a stage that cannot flip the verdict

Pre-register an experiment's stopping point alongside its decision rule; once the rule resolves, any further arm or stage that cannot change the verdict is pure spend rationalized as rigor ("for fidelity", "for completeness"). Incident 2026-07-09 (review-gate bench): re-running a reconstructed pipeline's verify stage after both arms had already answered cost 218k tokens and changed nothing.

## Duplication Anti-Pattern: guarding mirrors where an import is reachable

A test asserting copies agree feels equivalent to single-sourcing, but **a guard can only pin what you
already knew to enumerate**: every mirror you missed stays unguarded and reads as covered. An **import**
has no list — drift becomes unrepresentable for every consumer, found or not.

Rule: **when an import is reachable, single-source — do not guard.** Reserve guards for a genuine
unreachable import (a cycle, a build boundary, `.sql`/`.yaml`/generated output) and say which applies.
Recognition cue: "we'll add a guard so they can't drift" — check whether *can't* means *unrepresentable* or *listed*.

## Scoping Anti-Pattern: an artifact's name is not its scope

A hook named as "one budget gate" carried four independent signals; deleting it as a clean removal would
have dropped three unrelated checks. Rule: before offering removal (or counting coverage) of a named
artifact, **grep its body for distinct signals** and count those, not files.

## Transplant Anti-Pattern: a convention adopted without its home problem

A well-sourced convention solves the problem it was BUILT for; transplanted into a different one it can
undo the fix in flight. Rule: **state the convention's home problem in one line and compare it to yours
before recommending it** — if they differ, show the transplant's output value next to the current one.
Recognition cue: the argument is about pedigree, not your problem's shape.

## Seam Anti-Pattern: patching the reader list instead of moving the attach point down a layer

When a "ONE seam" claim collapses because recon finds N readers, the reflex is to attach at all N. Rule:
**look for the layer where the single seam becomes true again** (what do all N readers consume downstream?)
before accepting an N-site design. Cue: a plan step growing from "edit here" to four sites while the invariant stays one sentence.

## Reporting Anti-Pattern: a probe's reading line authored as the finding it was built to display

A probe built to display a prior finding invites writing its interpretation line before any output exists,
so it cannot contradict its own summary. Rule: **write the interpretation only after the first run**, off
the numbers that came back. Cue: a summary `console.log` committed in the edit that created the measurement.

## Delegation Anti-Pattern: a partial result from an outside turn reads as a finished one

Bulk generation handed to an external turn comes back covering a fraction of the set and looks complete; a
firmer "do ALL of them" just returns a different fraction.
**Rule: make the RECEIVING repo compute the denominator, and refuse on the shortfall** — build the artifact
from a tracked manifest so a missing item ships as a loud placeholder and the coverage check goes red.
