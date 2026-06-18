# Budget hook: exact *and* portable token accounting

**Date:** 2026-06-18
**Status:** Implemented (claudeconf, tasks 1–5); dotfiles follow-up (tasks 6–7) pending a dotfiles-cwd session
**Topic:** Replace the `bytes/4` proxy in `impag-budget-check.py` with inlined,
exact, compaction-aware token counting — with zero new dependencies.

## Problem

The shipped `impag-budget-check.py` estimates context tokens from transcript
file size (`bytes / 4`). Measured against a real parser this over-reads by
~1.4–1.8× on live sessions and ~2.4–3.9× post-compaction (the `.jsonl` retains
evicted history; real context resets on compact). Consequences:

- The hook trips early on live sessions (acceptable for a "wrap up" governor).
- In long compacted sessions it **false-fires** and keeps climbing.
- The docs carry an honesty caveat and label an "accurate version" as an
  optional upgrade requiring a private package.

The premise behind shipping `bytes/4` — *"the accurate version needs the private
`token_monitor` package, which isn't portable"* — **is false.**

## Key finding

`token_monitor.parser.parse_last_turn` (the import the portable hook dropped) is
**~40 lines of pure stdlib** (`json`, `os`). It does not tokenize anything. It:

1. Seeks the last 64 KB of the transcript (`f.seek(size - 65536)`).
2. Scans lines in reverse for the last `type == "assistant"` object.
3. Reads that turn's `message.usage` and returns
   `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`.

Those `usage` numbers are the **exact token counts the Anthropic API reported**
for that turn. The result is exact, compaction-aware (a post-compact assistant
turn reports the reset context), and dependency-free.

**The statusline already uses this exact formula.** `statusline.sh:15` computes
`input_tokens + cache_creation_input_tokens + cache_read_input_tokens` from
`.context_window.current_usage` (fed by the harness on stdin). So the statusline
is exact while the hook is `bytes/4` — they "share the 130k mark" in *value*
only, not in *measurement*. Inlining `parse_last_turn` makes them agree by
construction.

## Chosen approach: inline the tail-reader

Replace `estimate_tokens(transcript_path)` in the hook with an inlined
`read_last_turn_context(transcript_path)` adapted from `parse_last_turn`. No new
imports beyond what the hook already has (`json`, `os`/`pathlib`).

### Why this over the alternatives

| Approach | Verdict |
|---|---|
| **Inline tail-reader** (chosen) | Exact, compaction-aware, zero deps, ~40 LOC, matches statusline. |
| Keep `bytes/4` | Rejected — the inaccuracy it documents is now avoidable. |
| Read usage from the PostToolUse stdin payload | Rejected — PostToolUse payload is not documented to carry `context_window.current_usage` (that field is statusline-specific); the transcript tail is the reliable, version-stable source. |
| `pip install token_monitor` / vendor the whole package | Rejected — not on PyPI, and only one trivial function is needed. Inlining ~40 LOC beats a dependency. |

### New function (shape)

```python
_TAIL_CHUNK = 65536  # last assistant turn is virtually always in the final few KB

def read_last_turn_context(transcript_path: Path) -> int:
    """Exact context tokens = the last assistant turn's reported usage.

    Reads only the tail of the transcript. Returns 0 if the tail has no
    assistant turn (fresh/empty session) → hook stays silent. Compaction-aware:
    a post-compact assistant turn reports the reset context, unlike file size.
    """
    try:
        size = transcript_path.stat().st_size
    except OSError:
        return 0
    if size == 0:
        return 0
    with open(transcript_path, "rb") as f:
        if size > _TAIL_CHUNK:
            f.seek(size - _TAIL_CHUNK)
            f.readline()  # discard possibly-partial first line
        tail = f.read().decode("utf-8", errors="replace")
    for line in reversed(tail.splitlines()):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") != "assistant":
            continue
        usage = (obj.get("message") or {}).get("usage")
        if not usage:
            continue
        return (
            usage.get("input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0)
        )
    return 0
```

This satisfies the hooks rule "bounded reads on transcript files" — it never
loads the full file (only the 64 KB tail), so peak memory is independent of
transcript size. It supersedes the previous `bytes/4` read which also avoided a
full read but was inaccurate.

## Edits by surface

1. **`.claude/hooks/impag-budget-check.py`**
   - Replace `estimate_tokens` + `BYTES_PER_TOKEN` with `read_last_turn_context`
     (+ `_TAIL_CHUNK`).
   - Rewrite the module docstring: drop the two "inaccuracy" bullets and the
     "optional upgrade" note; state it now reads exact, compaction-aware usage
     from the transcript tail with zero dependencies.
   - **Fallback gate decision:** `FALLBACK_PROBE_BYTES` (400 KB) is no longer
     load-bearing for *accuracy*. Keep it **only** as a latency floor on the
     non-commit fallback path (skip the tail-read on tiny sessions that cannot
     be near 130k), and reword its comment to say so — it no longer compensates
     for over-reading. The per-session sentinel dedup is unchanged. *(Open
     decision A — see below.)*
   - Keep: git-commit trigger, sentinel dedup, `session_id` sanitization,
     `additionalContext` JSON envelope, fail-open wrapper.

2. **`.claude/hooks/README.md`** — rewrite the "Portability note" (lines ~51–57)
   and the budget-governor "Measures" bullet (line ~36): exact usage from the
   transcript tail; no private dependency; no accuracy caveat. Note it now uses
   the same formula as the statusline.

3. **`README.md`** (lines ~44, ~48–49) — drop "portable `bytes/4` variant"
   framing; describe exact tail-parse. Strengthen the statusline-alignment
   sentence to "same *measurement*, not just the same threshold."

4. **`ADOPT.md`** (line ~73) — reconcile the budget-governor description with the
   exact measurement; remove any "conservative/early-trip" hedging tied to
   `bytes/4`.

5. **`docs/2026-06-18-claudeconf-design.md`** (lines ~130, ~134, ~141, ~147–154,
   ~195, ~209) — update the budget-hook section and the "Dependency" /
   "Portable budget-hook variant" decisions: `token_monitor` import replaced by
   an **inlined stdlib tail-reader** (not by `bytes/4`); exact and portable, no
   tradeoff. This is a superseding-doc edit — fold the load-bearing rationale
   into the updated text before leaving the old wording behind.

## Second target: collapse the dotfiles hook into the same inline solution

There are **two** copies of this hook, and inlining the tail-reader makes the
distinction between them vanish:

- **claudeconf** `.claude/hooks/impag-budget-check.py` — the shipped *portable*
  variant (`bytes/4`, no dependency, documented accuracy caveat).
- **dotfiles** `~/projects/dotfiles/claude/.claude/hooks/impag-budget-check.py`
  (stowed to `~/.claude/hooks/`) — the author's *real* variant. Its only extra
  complexity is exactly what we are eliminating:
  - **Line 31** `from token_monitor.parser import parse_last_turn` — a hard
    top-level dependency on an editable-installed, non-PyPI private package.
  - **`pyrightconfig.json`** next to it: `{"extraPaths": ["../../../../token-monitor"]}`
    exists *solely* to make pyright resolve that import.

The whole reason claudeconf shipped a separate "portable variant with a tradeoff"
was to dodge this dependency. Inlining `read_last_turn_context` in **both** files
makes them **byte-for-byte identical**, exact, and dependency-free — the
two-variant split (and its documentation burden) disappears.

### Edits (dotfiles repo — separate from claudeconf)

6. **`dotfiles/claude/.claude/hooks/impag-budget-check.py`**
   - Delete the `from token_monitor.parser import parse_last_turn` import.
   - Add the inlined `read_last_turn_context` + `_TAIL_CHUNK` (same code as the
     claudeconf hook; replace `parse_last_turn(str(p)).total_context` with
     `read_last_turn_context(p)`).
   - Update the docstring's "Token accounting via `token_monitor`…" paragraph to
     describe the inlined tail-read. Keep the FALLBACK_PROBE_BYTES comment's
     intent but drop the "skip the full parse" framing.
7. **`dotfiles/claude/.claude/hooks/pyrightconfig.json`** — remove the now-dead
   `extraPaths` entry. If only `pythonVersion` remains and is the default, the
   file can be deleted; otherwise keep it trimmed. *(Open decision C.)*

The standalone `token-monitor` CLI (`report.py`, `cli.py`) is unaffected — it
keeps its own copy of `parse_last_turn`; only the *hook's* dependency on it is
severed.

### Cross-project execution note

These two edits land in the **dotfiles** git repo, not claudeconf. Per the
single-file-one-off vs. multi-file rule, this is a 2-file change — run and commit
it from a **dotfiles-cwd session**, edit the **source** under
`projects/dotfiles/...` (never the `~/.claude/...` stow symlink — readonly /
wrong inode), and commit it **separately** from the claudeconf commit. After
editing, run the dotfiles verification sweep (JSON-parse `pyrightconfig.json`,
resolve the stow symlink, confirm `~/.claude/hooks/impag-budget-check.py` points
at the edited source).

## Verification

- **Isolation test (block path):** synthesize a tiny JSONL whose last assistant
  turn has `usage` summing ≥130k, pipe a `git commit` PostToolUse payload
  pointing at it, assert the `additionalContext` reminder fires.
- **Isolation test (silent path):** same with usage < 130k → no output.
- **Compaction regression:** a JSONL with a large pre-compact prefix but a final
  assistant turn reporting < 130k must stay **silent** (the case `bytes/4`
  false-fired on). This is the headline behavioral fix — assert it explicitly.
- **Empty/garbage tail:** no assistant turn → returns 0 → silent, exit 0.
- **Fail-open:** unreadable transcript path → exit 0, no crash.
- **Cross-surface grep:** after edits, `grep -rn "bytes/4\|BYTES_PER_TOKEN\|
  optional upgrade\|token_monitor"` should return only intentional historical
  mentions (e.g. design-doc decision log noting the change), no live claims.
- **Convergence check:** `diff` the token-counting region of the claudeconf and
  dotfiles hooks — `read_last_turn_context` + `_TAIL_CHUNK` should be identical.
  Confirm `~/.claude/hooks/impag-budget-check.py` no longer imports
  `token_monitor` and runs clean with the `token-monitor` package uninstalled
  (simulate by running the isolation tests in an env without it on `sys.path`).

## Open decisions

- **A — Fallback latency floor.** Keep `FALLBACK_PROBE_BYTES` as a pure latency
  guard (recommended: yes — a 64 KB tail-read on every non-commit Bash call in a
  large session is cheap but not free, and tiny sessions can't be near 130k), or
  drop it for simplicity? Recommendation: **keep, reworded.**
- **B — Statusline source of truth.** Leave `statusline.sh` as-is (it reads live
  `current_usage` from the harness, which is the freshest source). The hook
  reads the transcript tail because PostToolUse has no `current_usage` field.
  These two exact sources can differ by at most the in-flight turn — acceptable.
  Recommendation: **no statusline change.**
- **C — `pyrightconfig.json` after the import is gone.** Delete the file (only
  `pythonVersion: "3.12"` would remain, which is the default), or keep it
  trimmed to `pythonVersion` for explicitness? Recommendation: **delete** — once
  `extraPaths` is gone it carries no information pyright doesn't already infer.

## Out of scope

- Changing the 130k/160k thresholds or the 200k session budget.
- Vendoring or installing the rest of `token_monitor` (only the tail-reader is
  needed).
- Any change to the git-commit trigger regex or the sentinel/dedup mechanics.
```
