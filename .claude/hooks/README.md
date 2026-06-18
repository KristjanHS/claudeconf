# .claude/hooks — Claude Code runtime hooks

These are **Claude Code runtime hooks**: scripts the Claude Code harness runs at
lifecycle events (compaction, session start, tool use). They are wired in
`.claude/settings.json`. Copy the ones you want into your own `~/.claude/hooks/`
and merge the matching `settings.json` block by hand.

> **Two `hooks/` directories — don't conflate them.** This directory is Claude
> Code **runtime** hooks; the repo-root `hooks/` is **git** hooks (the secret
> gate). Full table in the [README](../../README.md#two-hooks-directories--dont-conflate-them).

**Every hook here fails open** (`try: main(); except Exception: pass;
sys.exit(0)`). A hook bug must never block compaction, session start, or a tool
call — the cost of a crash during compaction is worse than the cost of a missed
check.

## The hooks

| File | Event (matcher) | What it does + why it saves context |
|---|---|---|
| `pre-compact.py` | `PreCompact` | Just before compaction, snapshots the transcript plus the active plan and todo state to a sidecar under `~/.claude/projects/<cwd-slug>/snapshots/`. Compaction keeps ~12% of the window and the 9-section summary can drop load-bearing reasoning; the sidecar is the full insurance copy. |
| `post-compact-restore.py` | `SessionStart` (`compact\|resume`) | Reads the newest snapshot and prints its recovery pointer (active plan, current task, where the full pre-compact transcript lives). Compaction doesn't re-inject the startup skill listing or subdirectory `CLAUDE.md` files, so Claude re-orients from a cheap pointer instead of re-deriving lost state. |
| `session-start-health.py` | `SessionStart` (`startup`) | Warns when any `MEMORY.md` exceeds 180 lines (Claude Code silently drops memory past ~200, so the warning lands early) and garbage-collects stale budget-hook sentinels. |
| `docs-bloat-gate.py` | `PreToolUse` (`Write\|Edit\|Bash`) | Blocks bloated `.md` writes at write time, so they never enter context in a future session. Three signals (any blocks): **S2** AI-slop stoplist phrase in net-added text (unbypassable); **S3** lexical density < 0.45 on a >100-char addition (unbypassable); **S1** char-delta over a tier cap (rule<50 lines=150, doc=800, spec=2000 chars) — bypassable, opt-in per project. Memory paths are exempt. Self-contained: the slop list and density tokenizer are inlined, no external import. |
| `impag-budget-check.py` | `PostToolUse` (`Bash`) | Injects a wrap-up reminder when accumulated context exceeds 130k tokens; detail below. |

## The budget governor — `impag-budget-check.py`

`impag-budget-check.py` is a `PostToolUse` hook on `Bash` that makes a long
`/impag` run stop taking new work before the session hits its context cliff:

1. **Triggers** — primary: a `git commit` (the natural task boundary). Fallback:
   any `Bash` call once the transcript exceeds a byte floor (a pure latency
   guard — small sessions can't be near 130k), so a working-tree-only session
   that never commits is still caught.
2. **Measures** exact context usage by parsing the last assistant turn's
   reported `usage` from the transcript tail (`input_tokens +
   cache_creation_input_tokens + cache_read_input_tokens`). Compaction-aware and
   bounded — reads only the final 64 KB, never the whole file.
3. **Hard-stop at 130k tokens** — silent below that by design; at >=130k it
   injects (via the `additionalContext` JSON envelope, because plain
   `PostToolUse` stdout reaches only the Ctrl-R transcript, not Claude's context)
   a wrap-up reminder: finish in-flight work, save remaining tasks to project
   state, then run code review then finishing-a-development-branch then retro.
4. **Fail-open** — any error exits 0; never blocks a commit.

The hook and `statusline.sh` **share the 130k mark _and_ the measurement**
(yellow at 130k, red at 160k): both sum `input_tokens +
cache_creation_input_tokens + cache_read_input_tokens`, so the *visual* warning
and the *automated* wrap-up fire off the same number, not just the same
threshold.

### Dependency note

None. The hook reads exact, compaction-aware usage from the transcript tail with
stdlib `json` only. (The author's private repo once imported
`token_monitor.parser.parse_last_turn` for this; that function is ~40 lines of
pure stdlib and is inlined here as `read_last_turn_context`, so there is no
private dependency to reinstate and no accuracy caveat.)

## Trying a hook in isolation

Each hook reads a JSON event payload on stdin. Example for the bloat gate:

```sh
echo '{"tool_name":"Write","tool_input":{"file_path":"/tmp/scratch.md","content":"We should leverage this approach."}}' \
  | python3 ~/.claude/hooks/docs-bloat-gate.py
echo "exit code: $?"   # 2 = blocked, 0 = allowed; stderr carries the reason
```

## Automated tests

Hook behaviour is pinned by a pytest suite in `tests/` (run `pytest` from the
repo root). `tests/test_impag_budget_check.py` covers the budget governor:
the exact tail-reader, the block/silent thresholds, the compaction regression,
and fail-open. Add cases there rather than scripting throwaway checks.
