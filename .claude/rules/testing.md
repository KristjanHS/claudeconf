---
description: "Rules for writing, reviewing, or discussing tests — test value gate, ratio discipline, pytest defaults"
paths:
  - "tests/**"
  - "**/test_*.py"
  - "**/*_test.py"
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

For stdlib-only CLI tools, aim for 1:1 to 2:1 test-to-production line ratio. If >3:1, review for bloat.

## Reducing test runtime

When a suite is slow, prefer deleting low-value tests (apply the 5-check gate) over hiding them behind markers (`@pytest.mark.slow` + default-exclude). Marker splits hide cost; they don't reduce it, and low-signal tests stay on the CI bill. Also look for unshared fixtures — multiple tests running the same expensive setup (subprocess calls, recalc, fixture rebuilds) are the usual hot spots. `pytest --durations=25` exposes them.

Session/module fixtures that mutate a file (recalc, rebuild, seed) must return the mutated artifact (path or loaded object), not just metadata. If the fixture returns only stats/JSON, every downstream caller that needs to read the mutated file has to re-do the work — duplicating the expensive setup the fixture was meant to amortize.

When migrating a module fixture to a session fixture, verify via full-suite wall-clock delta (not `--durations` top-N). `pytest --durations=N` attributes session-fixture setup cost to the *first* test in the run that triggers the chain — alphabetical ordering often keeps the migrated test at the top of durations even though total runtime dropped. In-isolation runs show zero savings because the session fixture still builds from scratch; savings only materialize when a sibling consumer already triggered the chain.

**External-process tests go in a manual tier from day one.** Tests that `docker exec`, `kubectl`, drive a headless browser, or hit a real network service carry seconds of per-test overhead even when the skip-guard fires — the readiness probe itself is expensive. Gate them behind an opt-in target (`tests/manual/*.bats`, `pytest -m e2e`, `make test-e2e`) and keep them out of the default suite + pre-push. A skip-clean test that adds 5s × N tests to every default run trains users to `--no-verify`. Move at the commit that adds the test, not after someone complains.

**Debug slow suites by per-file timing, not output-channel intuition.** When a suite regresses from fast to slow, time each file individually (`for f in tests/*.bats; do time bats "$f"; done` or `pytest --durations=0 tests/<file>`) to find the hot spot before hypothesizing about buffering/output filtering. Output buffers make a slow run *look* hung but don't cause the slowness — fixing the display without fixing the timing papers over the symptom.

**`unittest.mock.patch("heavy.module.attr", ...)` triggers the real import of `heavy.module`.** Even though the patch then replaces `attr` with a fake, the dotted-path resolver imports the parent to *find* the attribute. For modules whose import is multi-second (large ML/data-science packages), this pays the full import cost in a test that never exercises the real code.

**Symptom:** `--durations` shows one outlier test in the family at N seconds and the rest at <0.01s. The outlier is whichever test ran first — subsequent tests get the cached import for free. Looks asymmetric; isn't.

**Confirm:** time the import standalone (`python -c "import time; t=time.perf_counter(); from heavy.module import attr; print(time.perf_counter()-t)"`). If it matches the slow test's duration, the patch is the cause.

**Fix:** install a `sys.modules` stub via `monkeypatch.setitem` before calling the SUT, so the SUT's lazy `from heavy.module import attr` resolves to a fake. Stub both the leaf and its parent package — CPython's import machinery walks parents during resolution. The SUT must lazy-import inside the function body, not at module top, or the cost was already paid at test-collection time and stubbing later doesn't help.

## External tool skip guards

When a test skips on a missing binary, canary-test the tool on trivial input (`echo '{}' | yq .`) rather than relying on `command -v` alone. A corrupted install can present as installed but fail on every real call — `command -v` returns 0, the assertion under test fails, and you get a false negative instead of a clean skip.

## Before deleting on coverage grounds

Deleting a unit test on "integration covers it" grounds requires grepping the cited integration caller to verify it exercises the same code branches (input shape, formula form, edge cases) — prod paths often differ from test paths. "Covered elsewhere" without a grep is the strongest predictor of a silent coverage drop.

## Pruning / removal tests need a bystander

When testing code that removes or filters items ("orphan pruning", "remove stale entries", "drop unknown keys"), the test MUST include at least one item that is NOT supposed to be removed and assert it survives with value intact. A target-only assertion (`assert target not in result`) passes even if the pruning loop drops every item — the test proves nothing about selectivity. The bystander assertion is the real correctness gate.

For regex/pattern-filter tests specifically, the bystander must be an *adjacent-but-non-matching* input — one that shares substrings with a positive case so a broken anchor or `\b` boundary surfaces. A far-miss bystander (unrelated prose) proves only "doesn't fire on unrelated input"; an adjacent near-miss proves the boundary is correct.

For **rearrangement-preserving operations** (swap passes, stable sorts, permutation-preserving transforms), the bystander invariant is *set/multiset equality*, not element-identity. Asserting element-by-element equality on the complement fails spuriously because the op is *allowed* to rearrange there. Target-only + strict-complement = false red; target-only + multiset-complement = correct.

## Time-dependent expected values

Tests whose expected values depend on `date.today()` (current month, current year, "days since X") MUST derive them at runtime from the same formula the production code uses — never hardcode literals like `2026` or `month 5`. Hardcoded date values silently rot: pass today, fail in six months with no warning. If the derivation is non-trivial, skip gracefully when the window is impossible (e.g. `current_month < 3`) rather than asserting against stale ground truth.

## Bats files

Do not validate `.bats` files with `bash -n` — bats `@test` syntax is not standard bash and will always report syntax errors. Use `bats` directly to run and validate.

**Path assertions:** under bats, `$HOME` resolves to a tmpdir inside `/tmp/`. Negative assertions like `[[ "$path" != *"/tmp/"* ]]` false-positive even when production code is correct (the *expected* path also lives under `/tmp/$HOME/...`). Assert the expected prefix instead.
