# Python Refactor Gotchas — deep dives

Pulled from `~/.claude/rules/python-refactors.md` when you're mid-refactor and need the mechanism +
worked example for a specific trap. The rule keeps the index and the directive; the bodies here carry only
mechanism and examples. Sections match the rule's index numbers.

## 1. Lazy imports: scan the whole file, not just the top

Typical hiding places: `main()` and CLI entry points.

## 2. Collapsing isinstance/type guards: `if x and y` silently drops legitimate zero

When simplifying a defensive guard like `if total and completed and isinstance(total,(int,float)) and total>0:`
down to `if total and completed:`, a download-progress frame with `completed=0` (the real first frame) is
skipped. Fix: `if total and completed is not None:`. Keep truthiness only on operands where falsy genuinely
means "skip" (here `total` falsy ⇒ no denominator).

## 3. Tightening optional → required params

Run `pytest tests/ -q` before committing. If fixtures break, put the fallback in the orchestrator (single
point); don't sprinkle it into every fixture and don't revert.

**Dual-caller gotcha:** a builder with BOTH an orchestrator callsite AND bare test-fixture calls has a
fallback that is load-bearing for fixtures even when the orchestrator covers it
(`grep -rn "build_foo\b" tests/`). Orchestrator-only builders can be tightened freely.

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

**Companion gotcha:** a TYPE_CHECKING-only symbol (e.g. `from faster_whisper import Segment` under
`if TYPE_CHECKING:`) raises `NameError` at runtime when used as `cast(Segment, val)`. Use `cast(Any, val)`
(cheapest), `cast("Segment", val)` (string form, defers resolution), or move the import out of
`TYPE_CHECKING` if it's runtime-importable.

## 5. Constant renames: guard against shared-suffix aliasing

Example: `TOTAL_COLS → COLS_PER_YEAR` also rewrites `RP_TOTAL_COLS → RP_COLS_PER_YEAR`, invisible in the
diffstat. More than one sibling hit → switch to single-occurrence Edits, or extend `old_string` with context.

## 6. Removing exported constants: grep `tests/**` imports first

Staged plans that cite specific test files by name miss non-listed sibling test files that still import the
removed symbol. Sweep: `grep -rn "\bNAME\b" tests/` (or Grep with `type: py`).

## 7. Renaming a function parameter: grep `tests/**` for keyword callers

Positional callers are fine. A type-checker only flags callers in dirs it covers — if `include`/`exclude`
scopes it to app code (e.g. pyright `include=[backend]`), test and fixture callers are invisible. Worse, the
broken callers often sit in network-gated tests (`integration/`, `e2e/`) outside the default `unit` suite and
pre-commit, so the `TypeError` surfaces only against a live stack. The fresh-subagent code-reviewer is the
backstop that caught this when pyright + `make unit` both passed.

## 8. Mass kwarg drops: `replace_all` within a file, sed only across files

**Why not sed inside a single file:** sed rewrites the text your pending `old_string` anchors point at, so the
next `Edit` on that file fails with `String to replace not found` — which reads like a bad anchor guess rather
than staleness, and invites verbatim retries that bill as output tokens (see `edit-and-plan-gotchas.md` §
write-error taxonomy). `Edit(replace_all=true)` buys the same one-call economy without burning read state.

**Why not per-site Edits:** PostToolUse pyright/ruff hooks re-run after every Edit and dump full error listings. During a
signature sweep the tree is non-compiling mid-flight, so 20+ per-site Edits = 5–10k tokens of redundant hook
output per signature change.

For mechanical rewrites across many files, dispatch a general-purpose subagent so its intermediate-state hook
output stays in its context, not yours.

## 9. Pre-declared imports echo F401 across every subsequent Edit

A pre-declared unused import makes ruff fire `F401` on every unrelated Edit's PostToolUse hook until the usage
Edit lands, echoing the same warning block 5–10× into tool-result context. If you must pre-declare, use the
symbol with a `_ = NEW_SYM` no-op or add `# ruff: noqa: F401` on the line until real usage lands.

**Inverse direction (deletes):** an Edit that drops the import while a consumer survives fires pyright
`reportUndefinedVariable` + ruff `F821` on every reference, dumping ~20–40 lines of "Undefined name" frames
per symbol through the PostToolUse hook.

## 10. Bulk regex over `except: pass` swallowers

Converting silent swallowers (e.g. `except Exception: pass  # nosec B110`) to logged versions in bulk:

**(a)** The naive shape `except <X>:\n<ws>pass...` doesn't match `except <X>:\n<ws># note\n<ws>pass...`. After
the first pass, re-grep the target marker (`pass.*nosec`) and confirm 0 hits — don't trust the substitution count.

**(b)** Feeding the inline `# nosec B110 - <reason>` text into `LOGGER.debug("<reason>: %s", exc)` makes
repeated reasons ("cleanup", "transaction commit") emit the same DEBUG line from N sites. After the pass, run:

```sh
grep -oE 'LOGGER\.\w+\("[^"]*"' <file> | sort | uniq -c | awk '$1>1'
```

For each duplicate, prefix with the enclosing function or migration number (e.g.
`"migration 6 cleanup: run_metrics drop failed: %s"`).

## 11. Distinguish transitional aliases from cross-semantic aliases

(a) **Transitional**: old names retire when consumers migrate; tag with "retire after Stage N".
(b) **Cross-semantic**: the old name is canonical in its original context and the new one in a new context;
both alias the same value indefinitely. Before tagging an alias transitional, grep its consumers' use-site
comments and headers — if the consumer's context legitimately reads under the old name (e.g. a Plan sheet's
row-monthly-SUM column sharing a slot with Actuals' Slope), the alias is permanent and its comment should
describe the cross-semantic role.

## 12. Consolidating parallel implementations: copy from the LIVE path, not the canonical-looking one

The "canonical-looking" inline implementation in the most-prominent class is often unreachable —
`get_default_executor` overrides, dispatch indirection, or per-step `execute` overrides route live traffic
through a thinner delegating wrapper that *looks* secondary. The dead version looks more complete precisely
because it never had to delegate.

**How to apply:** trace the dispatch in code — start from where each Step/Executor is constructed, follow
`get_default_executor()` / `__init__` overrides, confirm with a callgraph grep. Your own commit message saying
"X was dead" is a load-bearing signal. A snapshot/equivalence gate under defaults (`ac=1`,
`target_channels=1`) won't catch a swap that differs only in parametric branches.

**Dead-copy example:** a `RAG_FAKE_ANSWER` hook lived in `answer()` + two presentation surfaces; both
surfaces resolved fake-mode and returned *before* calling `answer()`, and no test set the env var while calling
`answer()` directly — so the core copy was dead, a free deletion a plan had mislabelled as "surgery forcing
test rewrites". Sweep: `grep -n` the trigger (env var / flag / branch) across every caller + `tests/**`. Don't
force the concern *into* the core to "unify" — removing the dead copy IS the consolidation.

**Module-level side effects gotcha:** when collapsing N `Registry.register(...)` calls (each running a
`LOGGER.debug` on call) into a single dict literal, do NOT introduce a single module-level
`LOGGER.info("Registered N…")` at the end — it fires once per *import* (test discovery, every script), not
once per registration. Either drop it entirely (the count is visible in the literal) or keep `DEBUG`.

## 13. "Concise-ifying" a module-level sequence constant into a generator expression

`RETRY_BACKOFF = [1, 2, 4, 8]` → `RETRY_BACKOFF = (2 ** i for i in range(4))` creates one generator at
import, shared process-wide. The damage lands in a file the diff never touches:

```python
def call_with_retries(fn, *a):
    last = None
    for delay in settings.RETRY_BACKOFF:   # resumes the SAME exhausted generator
        try: return fn(*a)
        except TransientError as e: last = e; time.sleep(delay)
    raise last                             # loop never ran → last is None → TypeError
```

Every call consumes at least one value (a *successful* first attempt still burns one). After four calls the
generator is empty, `fn` is never invoked, and `raise last` with `last is None` →
`TypeError: exceptions must derive from BaseException` — far from the one-line diff, on a call that should
have succeeded.

**Fix:** `tuple(2 ** i for i in range(4))` or `[2 ** i for i in range(4)]`. **Review cue:** the bug is
invisible in the diff — grep the constant's consumers. A test that makes fewer calls than the sequence is
long stays green.
