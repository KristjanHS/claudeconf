---
description: "Rules for writing, reviewing, or discussing tests — test value gate, ratio discipline, pytest defaults"
paths:
  - "tests/**"
  - "**/test_*.py"
  - "**/*_test.py"
  - "**/*.test.ts"
  - "**/*.test.js"
  - "**/*.spec.ts"
  - "**/*.bats"
---
# Testing

Before writing any test, pass this gate:

1. **Is this testing MY code or the language?** If the test only verifies `len()`, `sum()`, `max()`, dict construction, or dataclass defaults — don't write it.
2. **Is this already covered?** If a higher-layer test exercises this code path, a unit test adds maintenance cost without coverage.
3. **Could this test ever fail from a real bug?** If the only way it fails is deleting the code entirely, it's testing existence, not behavior.
4. **Is this testing a trivial function too thoroughly?** Simple functions (<10 lines, ≤3 paths): 1-3 tests suffice.
5. **Am I testing an impossible input?** If the input can't occur given upstream guarantees, skip it.

When in doubt: one test per meaningful behavior, not one test per code path.

**A green test proves nothing until its fixture reaches the regime where the code would be wrong.** Eleven forms, all corollaries of value-gate check 3 — mechanisms and worked examples in the deep-dive:

- **Regression test** — arrange inputs so the *old* implementation produces the wrong answer; if both old and new pass, it guards nothing.
- **Property test** — name the regime that would BREAK the invariant and put a fixture there; add a vacuity guard (some input must change the output).
- **"Duplicate" test** — trace each expected value to its origin before deleting either; a survivor whose expected value is emitted by the function under test is circular, and pins wiring rather than behavior.
- **Cross-port parity** — compare *shape* before comparing elementwise, or the comparator is blind to one port dropping a row where the other emits null-in-place.
- **"Two sources must agree"** — check the test reads BOTH; a constant re-stated in the test file is a third source, so the pin can never see the two disagree. Prefer single-sourcing the value — that dissolves the drift class instead of asserting against it. **Whenever the import is reachable, take it over the guard**: a guard pins only the drifts you already knew to enumerate, while the import surfaces the ones no sweep listed.
- **Planted-bug fixture** (benchmarking a reviewer/linter/agent) — prove by *execution* that each planted bug fires and each decoy does **not**, before scoring anything. An asserted answer key leaks real bugs into the decoys and silently inverts the precision score.
- **Decline-only suite** — a suite that pins only the DECLINE/negative paths passes unchanged if the feature returns empty unconditionally. Every feature with an accept path owes one test that goes red when it no-ops.
- **Mutation check** — the runner stops at the *first* failing assertion, so an earlier one in the same test masks the witness you meant to prove red. Neutralise the assertions preceding it, confirm the intended one fails, then restore.
- **Brand-isolation** — a `@ts-expect-error` brand-type test must ISOLATE the brand: asserting a `Branded`→`Base` assignment is VACUOUS if `Base` already accepts the value; assign something the target type must REJECT, or the `@ts-expect-error` never bites.
- **Behavior-overturning change / "mirror X exactly" ruling** — a change that OVERTURNS an invariant needs the OLD-invariant pin REWRITTEN into the new contract's halves PLUS a DISCRIMINATING fixture; a "mirror X exactly" ruling binds the FLOOR/edge constants too, not just the happy path. Only a narrowly-shaped fixture red-demos it (a 1-value/1-leg case passes under BOTH the old and new floor — only the 2-leg case, where the floor differs, bites).
- **Contrastive ruling** — when a design ruling names rule X *in contrast to* a plausible alternative Y (pairwise vs asOf-anchored age bound), fixtures that pass under BOTH pin nothing; the owed test is the one that DISTINGUISHES X from Y, verified red by mutating the exact line the prose describes (deleting `cursor = row.date` left a 109-file suite green because gap/stale-only fixtures pass under both rules).

**Pin `now` in any date-dependent test.** Wall-clock fixtures are time-bombs: a test reading the system clock passes until the code gains a `now`-relative window (lookback, staleness gate, same-day cutoff), then reds on a calendar boundary no diff touched. Inject a FIXED `now` (fake clock / explicit `asOf` arg) into every date-dependent assertion — never let a fixture's freshness ride the wall clock.

For stdlib-only CLI tools, aim for 1:1 to 2:1 test-to-production line ratio. If >3:1, review for bloat.

**A check script is reusable, not a scratchpad throwaway.** A script written to test, debug, backtest, or falsify — even a one-off answering a single in-conversation question — encodes a re-runnable check (a regression guard, a liveness falsifier). Promote it into the repo following the local convention (a `scripts/` entry + a package script), have it call the REAL production function rather than reimplement the engine, typecheck it, and delete the scratchpad copy — a throwaway is lost next session and the check has to be re-derived.

---

**Writing or debugging the test *machinery* rather than the assertions, or about to delete a test on
"covered elsewhere" grounds?** → read `~/.claude/references/testing-deep-dives.md` for: slow-suite triage +
fixture amortization, the before-deleting-on-coverage grep check, the
`mock.patch` real-import cost, external-tool skip guards, the bystander assertion (pruning/filter/regex/
rearrangement tests), time-dependent expected values, and `.bats` quirks.
