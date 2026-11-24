---
name: Python refactors
description: Gotchas when refactoring Python imports and module structure
paths:
  - "**/*.py"
---

# Python Refactor Rules

Each refactor below has a recurring trap. The one-liner is the *recognition* cue; the **mechanism + worked
example** for each lives in `~/.claude/references/python-refactors-deep-dives.md` (numbers match).

**Before any import / module-structure / param / constant / signature / consolidation refactor, read the L3
deep-dive for the gotcha you're about to trigger** — the one-liner tells you *that* a trap exists, not how to
avoid it.

1. **Lazy imports** — imports inside `if`/`try`/function bodies are easy to miss; grep `^\s*(from|import)\s`
   across the whole file before declaring an import refactor done.
2. **Collapsing isinstance/type guards** — `if x and y` silently drops legitimate `0`/`""`/`0.0`; guard
   present-only operands with `is not None`, not truthiness (the falsy-zero trap).
3. **Tightening optional → required params** — removing a `None` default *moves* the fallback, doesn't erase
   it; check for bare test-fixture callers, relocate the fallback to the orchestrator.
4. **Storing `Literal`-typed params on `self`** — needs an inline annotation or pyright widens to the parent
   type and breaks `reportIncompatibleMethodOverride`; companion: `cast(X, val)` evaluates `X` at runtime.
5. **Constant renames** — `replace_all` on a short identifier silently rewrites shared-suffix siblings; grep
   `[A-Z_]*OLD_NAME\b` first.
6. **Removing exported constants** — grep `tests/**` imports first; pytest collection errors surface only at
   run time, pyright won't catch them once the export is gone.
7. **Renaming a function parameter** — breaks `oldname=` keyword callsites a scoped type-checker can't see;
   grep `oldname=` across app + `tests/**` (incl. network-gated suites) before committing.
8. **Mass kwarg drops (≥4 callsites)** — one `Edit(replace_all=true)` within a file, never per-file Edit (each
   echoes ~40 lines of mid-flight hook errors) and never `sed -i`; `sed` only for multi-file sweeps, re-Read
   after (why → `~/.claude/references/edit-and-plan-gotchas.md`).
9. **Pre-declared imports echo F401** — add a new import in the *same* Edit that first uses it; on deletes,
   drop the import in the same Edit that removes the last consumer.
10. **Bulk regex over `except: pass` swallowers** — regex misses comment-prefixed `pass`; mechanically derived
    log messages collapse onto the same string (de-dup by enclosing function).
11. **Transitional vs cross-semantic aliases** — don't tag a cross-semantic alias "retire after Stage N"; it's
    permanent and the tag creates phantom debt.
12. **Consolidating parallel implementations** — copy from the LIVE path, not the canonical-looking one; one
    of the N copies may be DEAD (grep callers for short-circuits first); watch module-level side effects.
13. **"Concise-ifying" a module-level sequence constant** — `[...]` → `(...)` makes a **one-shot generator**,
    not a tuple; per-call consumers drain it cumulatively and then silently iterate zero times. Use a tuple.
