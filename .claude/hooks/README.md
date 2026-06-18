# .claude/hooks — Claude Code runtime hooks

These are **Claude Code runtime hooks**: scripts the Claude Code harness runs at
lifecycle events (compaction, session start, tool use). They are wired in
`.claude/settings.json`. Copy the ones you want into your own `~/.claude/hooks/`
and merge the matching `settings.json` block by hand.

> **Two `hooks/` directories — don't conflate them.**
> - `.claude/hooks/` (this directory) = Claude Code runtime hooks — the
>   context-optimization content.
> - the repo-root `hooks/` = **git hooks** (the secret gate: gitleaks +
>   identity/path check, wired via `core.hooksPath`). Different mechanism,
>   different trigger.

**Every hook here fails open** (`try: main(); except Exception: pass;
sys.exit(0)`). A hook bug must never block compaction, session start, or a tool
call — the cost of a crash during compaction is worse than the cost of a missed
check.

## The hooks

| File | Event (matcher) | What it does + why it saves context |
|---|---|---|
| `pre-compact.py` | `PreCompact` | Just before compaction, snapshots the transcript plus the active plan and todo state to a sidecar under `~/.claude/projects/<cwd-slug>/snapshots/`. The 9-section compact summary can drop load-bearing reasoning; the sidecar is the insurance copy. |
| `post-compact-restore.py` | `SessionStart` (`compact\|resume`) | Reads the newest snapshot and prints its recovery pointer (active plan, current task, where the full pre-compact transcript lives). Claude re-orients from a cheap pointer instead of re-deriving lost state. |
| `session-start-health.py` | `SessionStart` (`startup`) | Warns when any `MEMORY.md` exceeds 180 lines (Claude Code silently drops memory past ~200, so the warning lands early) and garbage-collects stale budget-hook sentinels. |
| `docs-bloat-gate.py` | `PreToolUse` (`Write\|Edit\|Bash`) | Blocks bloated `.md` writes at write time, so they never enter context in a future session. Three signals (any blocks): **S2** AI-slop stoplist phrase in net-added text (unbypassable); **S3** lexical density < 0.45 on a >100-char addition (unbypassable); **S1** char-delta over a tier cap (rule<50 lines=150, doc=800, spec=2000 chars) — bypassable, opt-in per project. Memory paths are exempt. Self-contained: the slop list and density tokenizer are inlined, no external import. |
| `impag-budget-check.py` | `PostToolUse` (`Bash`) | The budget governor (see below). Already present in this repo. |

## The budget governor — `impag-budget-check.py`

`impag-budget-check.py` is a `PostToolUse` hook on `Bash` that makes a long
`/impag` run stop taking new work before the session hits its context cliff:

1. **Triggers** — primary: a `git commit` (the natural task boundary). Fallback:
   any `Bash` call once a cheap `transcript_bytes / 4` proxy crosses a floor, so
   a working-tree-only session that never commits is still caught.
2. **Measures** current context usage from the transcript size.
3. **Hard-stop at 130k tokens** — silent below that by design; at >=130k it
   injects (via the `additionalContext` JSON envelope, because plain
   `PostToolUse` stdout reaches only the Ctrl-R transcript, not Claude's context)
   a wrap-up reminder: finish in-flight work, save remaining tasks to project
   state, then run code review then finishing-a-development-branch then retro.
4. **Fail-open** — any error exits 0; never blocks a commit.

The **130k threshold is shared with `statusline.sh`** (yellow at 130k, red at
160k), so you get the *visual* warning and the *automated* wrap-up off the same
mark.

### Portability note

The author's private version imports `token_monitor.parser.parse_last_turn`
from an editable-installed package that is not on PyPI; copied as-is it raises
`ModuleNotFoundError`. The variant shipped here drops that import and uses the
`transcript_bytes / 4` estimate for the token count too — slightly less
accurate, zero dependencies, same pattern. To upgrade to exact accounting,
reinstate a real token count in `estimate_tokens` and keep everything else.

## Trying a hook in isolation

Each hook reads a JSON event payload on stdin. Example for the bloat gate:

```sh
echo '{"tool_name":"Write","tool_input":{"file_path":"/tmp/scratch.md","content":"We should leverage this approach."}}' \
  | python3 ~/.claude/hooks/docs-bloat-gate.py
echo "exit code: $?"   # 2 = blocked, 0 = allowed; stderr carries the reason
```
