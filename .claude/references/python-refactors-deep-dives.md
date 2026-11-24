# Python Refactor Gotchas — deep dives

Pulled from `~/.claude/rules/python-refactors.md` when you're mid-refactor and need the mechanism +
worked example for a specific trap. The rule keeps the index; the bodies live here. Sections match the
rule's index numbers.

## 1. Lazy imports: scan the whole file, not just the top

Imports inside `if`/`try`/function bodies (especially in `main()` and CLI entry points) are easy to miss.
Grep `^\s*(from|import)\s` across the whole file before declaring an import refactor done.

## 2. Collapsing isinstance/type guards: `if x and y` silently drops legitimate zero

When simplifying a defensive guard like `if total and completed and isinstance(total,(int,float)) and total>0:`
down to `if total and completed:`, the truthiness test drops valid `0`/`""`/`0.0` values — e.g. a
download-progress frame with `completed=0` (the real first frame) is skipped. Guard the operand you only need
*present* with `is not None`: `if total and completed is not None:`. Keep truthiness only on operands where
falsy genuinely means "skip" (here `total` falsy ⇒ no denominator). This is the falsy-zero trap and recurs
whenever you delete an `isinstance` ladder.

## 3. Tightening optional → required params

Removing a `None` default moves the fallback — it doesn't erase it. Run `pytest tests/ -q` before committing.
If fixtures break, relocate the fallback to the orchestrator (single point); don't sprinkle it into every
fixture and don't revert.

**Dual-caller gotcha:** a builder with BOTH an orchestrator callsite AND bare test-fixture calls has a
fallback that is load-bearing for fixtures even when the orchestrator covers it. Before removing,
`grep -rn "build_foo\b" tests/` to check for bare callers. Orchestrator-only builders can be tightened freely.

## 4. Storing `Literal`-typed params on `self` needs an inline annotation

Pyright widens `Literal[...]` → its parent type (typically `str`/`int`) when assigning to `self.attr` without
an explicit annotation, even if the source param is Literal-typed. A method override that returns `self.attr`
then fails `reportIncompatibleMethodOverride` against a Literal-declared base — the error reads "override
returns `tuple[str, str]`" despite every source being Literal-typed.

```python
def __init__(self, device: DeviceType):    # DeviceType = Literal["cpu", "cuda"]
    self.device: DeviceType = device       # NOT: self.device = device
```

Same gotcha for `list[tuple[..., DeviceType, ...]]` containers populated via `.append(...)` — annotate the
container generic; inferred-from-append widens to the parent type.

**Companion gotcha — `typing.cast(X, val)` evaluates `X` at runtime.** A TYPE_CHECKING-only symbol (e.g.
`from faster_whisper import Segment` under `if TYPE_CHECKING:`) raises `NameError` at runtime when used as
`cast(Segment, val)`. Use `cast(Any, val)` (cheapest), `cast("Segment", val)` (string form, defers
resolution), or move the import out of `TYPE_CHECKING` if it's runtime-importable.

## 5. Constant renames: guard against shared-suffix aliasing

`Edit` with `replace_all: true` on a short identifier silently rewrites sibling names that share the substring
(e.g. `TOTAL_COLS → COLS_PER_YEAR` also rewrites `RP_TOTAL_COLS → RP_COLS_PER_YEAR`). Invisible in the
diffstat.

Before `replace_all`, grep `[A-Z_]*OLD_NAME\b` for siblings. More than one hit → switch to single-occurrence
Edits, or extend `old_string` with context.

## 6. Removing exported constants: grep `tests/**` imports first

Deleting or renaming a module-level constant that was `from X import NAME`-exported requires a `tests/**`
import sweep *before* committing — pytest collection errors only surface when the test runs, and staged plans
that cite specific test files by name can miss non-listed sibling test files that still import the removed
symbol.

Before removing, run `grep -rn "\bNAME\b" tests/` (or via Grep with `type: py`). Pyright alone is
insufficient — it catches unused-import warnings in tests only after the import is resolvable, which it isn't
once the export is gone.

## 7. Renaming a function parameter: grep `tests/**` for keyword callers

Renaming a param breaks every `oldname=` keyword callsite (positional callers are fine). A type-checker only
flags callers in dirs it covers — if `include`/`exclude` scopes it to app code (e.g. pyright
`include=[backend]`), test and fixture callers are invisible and the rename looks clean until the suite runs.
Worse, the broken callers are often in network-gated tests (`integration/`, `e2e/`) that don't run in the
default `unit` suite or pre-commit, so the `TypeError` surfaces only against a live stack.

Before committing a param rename, `grep -rn "oldname=" backend/ frontend/ tests/ *.py` (or Grep `type: py`).
The fresh-subagent code-reviewer is the backstop that caught this when pyright + `make unit` both passed.

## 8. Mass kwarg drops: `replace_all` within a file, sed only across files

Dropping an identical kwarg from ≥4 callsites — never a separate Edit per site. **Within one file, use one
`Edit(replace_all=true)`** anchored on the shared invocation slice. Reach for `sed -i -e 's/.../.../g' <files>`
only when the sweep spans several files; sed and `replace_all` are *not* interchangeable.

**Why not sed inside a single file:** sed rewrites the text your pending `old_string` anchors point at, so the
next `Edit` on that file fails with `String to replace not found` — which reads like a bad anchor guess rather
than staleness, and invites verbatim retries that bill as output tokens (see `edit-and-plan-gotchas.md` §
write-error taxonomy). `Edit(replace_all=true)` buys the same one-call economy without burning read state.
**After any sed, treat that file's read state as burnt:** re-Read a narrow `offset`/`limit` window before the
next Edit on it.

**Why not per-site Edits:** PostToolUse pyright/ruff hooks re-run after every Edit and dump full error listings. During a
signature sweep the tree is non-compiling mid-flight, so each Edit echoes ~40 lines of expected errors into
tool-result context. 20+ per-site Edits = 5–10k tokens of redundant hook output per signature change.

**How to apply:** triggers on `def foo(..., kwarg=None, ...)` → `def foo(..., ...)` with ≥4 callsites.
Single file → one `Edit(replace_all=true)`, whatever the slice looks like. Multi-file sweep with an identical
`kwarg=kwarg` slice → sed, then re-Read any file you still intend to Edit. For
mechanical rewrites across many files, dispatch a general-purpose subagent so its intermediate-state hook
output stays in its context, not yours.

## 9. Pre-declared imports echo F401 across every subsequent Edit

When a multi-Edit refactor introduces a new import, add the `from X import NEW_SYM` line in the **same Edit**
that first uses `NEW_SYM` — not in an early "set up imports first" Edit. A pre-declared unused import makes
ruff fire `F401` on every subsequent unrelated Edit's PostToolUse hook until the usage Edit lands, echoing the
same warning block 5–10× into tool-result context.

If you must pre-declare, immediately use the symbol with a `_ = NEW_SYM` no-op or add `# ruff: noqa: F401` on
the line until real usage lands.

**Inverse direction (deletes):** drop the `from X import OLD_SYM` line in the **same Edit** that removes the
last consumer — not in an earlier "clean up imports" Edit. An orphaned consumer with a still-present import is
just `F401` (noisy), but an Edit that drops the import while the consumer survives fires pyright
`reportUndefinedVariable` + ruff `F821` on every reference, dumping ~20–40 lines of "Undefined name" frames
per symbol through the PostToolUse hook. Combine the paired drop into one Edit.

## 10. Bulk regex over `except: pass` swallowers

Converting silent exception swallowers (e.g. `except Exception: pass  # nosec B110`) to logged versions in
bulk: two gotchas.

**(a) Regex misses comment-prefixed variants.** The naive shape `except <X>:\n<ws>pass...` doesn't match
`except <X>:\n<ws># note\n<ws>pass...`, which is common when the swallow was previously documented. After the
first pass, re-grep the target marker (`pass.*nosec`, or whatever distinguishes the original) and confirm 0
hits — don't trust the substitution count.

**(b) Mechanically derived messages collapse onto the same string.** If you feed the inline
`# nosec B110 - <reason>` text into `LOGGER.debug("<reason>: %s", exc)`, repeated reasons ("cleanup",
"transaction commit") yield N call sites emitting the same DEBUG line, defeating call-site identity. After the
pass, run:

```sh
grep -oE 'LOGGER\.\w+\("[^"]*"' <file> | sort | uniq -c | awk '$1>1'
```

For each duplicate, prefix with the enclosing function or migration number (e.g.
`"migration 6 cleanup: run_metrics drop failed: %s"`).

## 11. Distinguish transitional aliases from cross-semantic aliases

Adding new names alongside old ones during a refactor produces two species. (a) **Transitional**: old names
will retire when consumers migrate; tag with "retire after Stage N". (b) **Cross-semantic**: old name is
canonical in its original context and the new name is canonical in a new context; both names alias the same
underlying value indefinitely. Tagging (b) as "retire after Stage N" creates phantom debt the next reviewer
feels obligated to repay. Before tagging an alias transitional, grep its consumers' use-site comments and
headers — if the consumer's context legitimately reads under the old name (e.g. a Plan sheet's
row-monthly-SUM column happens to share a slot with Actuals' Slope), the alias is permanent. The comment block
should describe the cross-semantic role, not promise retirement.

## 12. Consolidating parallel implementations: copy from the LIVE path, not the canonical-looking one

When a refactor collapses N parallel implementations of the same operation, identify which path was reached in
production BEFORE choosing which body to keep. The "canonical-looking" inline implementation in the
most-prominent class is often unreachable — `get_default_executor` overrides, dispatch indirection, or
per-step `execute` overrides route live traffic through a thinner delegating wrapper that *looks* secondary.
The dead version is usually more complete-looking precisely because it never had to delegate; copying it bakes
a parallel maintenance fork into the new structure.

**How to apply:** trace the dispatch in code, not in your head — start from the entry point each Step/Executor
is constructed at, follow `get_default_executor()` / `__init__` overrides, then confirm with a callgraph grep.
If your own commit message acknowledges "X was dead", that's a load-bearing signal: prefer the live function
as the body; if you must inline, copy from the live function. A snapshot/equivalence gate that runs under
defaults (`ac=1`, `target_channels=1`) will not catch a swap that differs only in parametric branches.

**One of the N copies may be DEAD, not just secondary — grep callers for short-circuits first.** Before
treating a consolidation as risky behavioral surgery, check whether each copy is even *reached*: a caller that
handles the concern inline and short-circuits before the call site makes the callee's copy unreachable.
(Seen: a `RAG_FAKE_ANSWER` hook lived in `answer()` + two presentation surfaces; both surfaces resolved
fake-mode and returned/printed *before* calling `answer()`, and no test set the env var while calling
`answer()` directly — so the core copy was dead.) A plan can mislabel deleting it as "surgery forcing test
rewrites" when it's a free deletion. Sweep: `grep -n` the trigger (env var / flag / branch) across every
caller + `tests/**`; if every caller short-circuits and no test exercises the callee's copy, delete it as dead
code. Corollary: don't force the concern *into* the core to "unify" when the surfaces legitimately render it
differently — removing the dead copy IS the consolidation.

**Module-level side effects gotcha:** when collapsing N `Registry.register(...)` calls (each running a
`LOGGER.debug` on call) into a single dict literal, do NOT introduce a single module-level
`LOGGER.info("Registered N…")` at the end — it fires once per *import* (test discovery, every script), not
once per registration. Either drop it entirely (the count is visible in the literal) or keep `DEBUG`.

## 13. "Concise-ifying" a module-level sequence constant into a generator expression

`RETRY_BACKOFF = [1, 2, 4, 8]` → `RETRY_BACKOFF = (2 ** i for i in range(4))` looks like a pure tidy-up: same
values, one expression. But `(...)` is a **generator expression**, not a tuple — a single mutable, one-shot
object created once at import and shared process-wide.

The damage lands in a file the diff never touches — whichever module does `for x in mod.CONST` per call:

```python
def call_with_retries(fn, *a):
    last = None
    for delay in settings.RETRY_BACKOFF:   # resumes the SAME exhausted generator
        try: return fn(*a)
        except TransientError as e: last = e; time.sleep(delay)
    raise last                             # loop never ran → last is None → TypeError
```

Every call consumes at least one value (a *successful* first attempt still burns one). After four calls the
generator is empty, the loop body never executes, `fn` is never invoked, and control falls to `raise last`
with `last is None` → `TypeError: exceptions must derive from BaseException` — a nonsense error, far from
the one-line diff that caused it, on a call that should have succeeded.

**Fix:** `tuple(2 ** i for i in range(4))` or `[2 ** i for i in range(4)]`. **Recognition cue:** a config
constant whose right-hand side gained parentheses. **Review cue:** the bug is invisible in the diff — you
must grep the constant's consumers. A test that makes fewer calls than the sequence is long stays green.
