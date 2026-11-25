# .claude/hooks - Claude Code runtime hooks

These are **Claude Code runtime hooks**: scripts the Claude Code harness runs at
lifecycle events (compaction, session start, tool use). They are wired in
`.claude/settings.json`. Copy the ones you want into your own `~/.claude/hooks/`
and merge the matching `settings.json` block by hand.

> **Two `hooks/` directories - don't conflate them.** This directory is Claude
> Code **runtime** hooks; the repo-root `hooks/` is **git** hooks (the secret
> gate). Full table in the [README](../../README.md#two-hooks-directories--dont-conflate-them).

**Every hook here fails open** (`try: main(); except Exception: pass;
sys.exit(0)`). A hook bug must never block compaction, session start, or a tool
call - the cost of a crash during compaction is worse than the cost of a missed
check.

## The hooks

| File | Event (matcher) | What it does + why it saves context |
|---|---|---|
| `pre-compact.py` | `PreCompact` | Just before compaction, snapshots the transcript plus the active plan and todo state to a sidecar under `~/.claude/projects/<cwd-slug>/snapshots/`. Compaction keeps ~12% of the window and the 9-section summary can drop load-bearing reasoning; the sidecar is the full insurance copy. |
| `post-compact-restore.py` | `SessionStart` (`compact\|resume`) | Reads the newest snapshot and prints its recovery pointer (active plan, current task, where the full pre-compact transcript lives). Compaction doesn't re-inject the startup skill listing or subdirectory `CLAUDE.md` files, so Claude re-orients from a cheap pointer instead of re-deriving lost state. |
| `docs-bloat-gate.py` | `PreToolUse` (`Write\|Edit\|Bash`) | Watches `.md` writes so bloat never enters context in a future session. Signals: **S2** AI-slop stoplist phrase in net-added text and **S3** lexical density < 0.45 on a >100-char addition are *advisory* - the write proceeds and a one-line nudge is fed back via `additionalContext`, throttled to once per signal per session; **W1** a new audit-style `docs/*.md` root file is likewise advisory. Only **S1** (char-delta over a tier cap: rule<50 lines=150, doc=800, spec=2000 chars) *blocks* - bypassable (N=3 override sentinels/session, brand-new gated file, or L2-heading carve-out), opt-in per project. Every fire is logged for tuning. Memory paths are exempt. Self-contained: the slop list and density tokenizer are inlined, no external import. |
| `impag-budget-check.py` | `PostToolUse` (`Bash`) | Injects a wrap-up reminder when accumulated context crosses `HARD_STOP_TOKENS`; detail below. |
| `destructive-bash-gate.py` | `PreToolUse` (`Bash`) | Blocks destructive commands that prefix-match deny rules miss; [section below](#destructive-bash-gatepy). |
| `external-process-test-gate.py` | `PreToolUse` (`Write\|Edit`) | Keeps docker/browser/HTTP tests in `tests/manual/`; [section below](#external-process-test-gatepy). |
| `agent-model-pin-gate.py` | `PreToolUse` (`Agent`) | Blocks an Agent call whose model family differs from the agent's pin; [section below](#agent-model-pin-gatepy). |
| `ruff-check.sh` | `PostToolUse` (`Write\|Edit`, `Bash`), `Stop`, `SubagentStop` | Lint ratchet against the committed baseline; [section below](#ruff-checksh). |

## The budget governor - `impag-budget-check.py`

`impag-budget-check.py` is a `PostToolUse` hook on `Bash` that makes a long
`/impag` run stop taking new work before the session hits its context cliff:

1. **Triggers** - primary: a `git commit` (the natural task boundary). Fallback:
   any `Bash` call once the transcript exceeds a byte floor (a pure latency
   guard - small sessions can't be near the bands), so a working-tree-only session
   that never commits is still caught.
2. **Measures** exact context usage by parsing the last assistant turn's
   reported `usage` from the transcript tail (`input_tokens +
   cache_creation_input_tokens + cache_read_input_tokens`). Compaction-aware and
   bounded - reads only the final 64 KB, never the whole file.
3. **Four graduated bands** (`BANDS` in the hook; values in the
   [measured table](../../README.md#-does-this-actually-work)) - three soft
   notices that say *keep going, no action*, each firing once per session on the
   way up, then a hard stop at `HARD_STOP_TOKENS` that repeats on every commit
   past it. Silent below the lowest soft band by design. Every band
   injects via the `additionalContext` JSON envelope, because plain `PostToolUse`
   stdout reaches only the Ctrl-R transcript, not Claude's context. The hard
   band's text is the operative one: do not start a new task, finish in-flight
   work, save remaining tasks to project state, then run code review, then finish
   the branch - and *record* a retro as owed rather than running one, because a
   retro at the hard stop costs more than it captures. A measured drop far below the
   session highwater is read as a compaction and re-arms the bands.
4. **Fail-open** - any error exits 0; never blocks a commit.

The hook and `statusline.sh` **share the hard-stop mark _and_ the measurement**
(the statusline turns yellow at the hook's `HARD_STOP_TOKENS`): both sum `input_tokens +
cache_creation_input_tokens + cache_read_input_tokens`, so the *visual* warning
and the *automated* wrap-up fire off the same number, not just the same
threshold.

### Dependency note

None. The hook reads exact, compaction-aware usage from the transcript tail with
stdlib `json` only. (An earlier tool once imported
`token_monitor.parser.parse_last_turn` for this; that function is ~40 lines of
pure stdlib and is inlined here as `read_last_turn_context`, so there is no
private dependency to reinstate and no accuracy caveat.)

## The guard hooks

Each guard below is self-documenting: its module docstring is the full spec.

### `destructive-bash-gate.py`

`PreToolUse` (`Bash`). Blocks (exit 2) the destructive class that prefix-match
deny rules can't catch: recursive `rm` on `/`, `~`, `$HOME`, bare-variable roots
or top-level system dirs (and any `--no-preserve-root`); a downloader piped or
substituted into a shell; write-actions into a `.ssh` dir. Write-actions into a
path guarded by an `Edit(...)` ask rule get an *ask*, never a block (needs
`~/.claude/lib/ask_paths.py`). Analysis is token-level, so text that only
*mentions* `rm -rf /` (commit messages, heredoc bodies) passes. Fails open on
errors and parse failures, except an unparseable command matching `RAW_DANGER`.
**No in-band bypass** - a genuinely intended command is run by the user, or the
user removes the hook from `settings.json`. Blocks log to
`~/.claude/state/destructive-bash-blocks.log`.

### `external-process-test-gate.py`

`PreToolUse` (`Write|Edit`), acting on `tests/**/*.py` except `tests/manual/**`,
`tests/__init__.py` and `tests/conftest.py`. Blocks test code that drives
heavyweight external systems - a `docker`/`playwright`/`selenium` import, a
`requests.<verb>(` call, or `subprocess`/`os.system` launching
`docker`/`kubectl`/`playwright`/`selenium` - so it lands in `tests/manual/` and
stays out of the default `pytest` run. A project's own toolchain
`subprocess.run` passes. **Override:** add
`<!-- external-process-test-gate-override: <reason of 10+ chars> -->` to the
content; overrides log to `~/.claude/logs/external-process-test-overrides.log`.

### `agent-model-pin-gate.py`

`PreToolUse` (`Agent`). Blocks (exit 2) an Agent call whose `model` family
(opus/sonnet/haiku/fable, from an alias or a full ID) differs from the `model:`
pin in the named subagent's definition - looked up in the project's
`.claude/agents/`, then `~/.claude/agents/`. **No in-band bypass**: the cheap
read-only tier is `Explore`, not a downshifted pinned agent. Fails open on
errors; blocks log to `~/.claude/state/agent-model-pin-blocks.log`.

### `ruff-check.sh`

`PostToolUse` on `Write|Edit` (lint + format) and on `Bash` with `--lint-only`
(`.py` files a Bash write left dirty), re-checked on `Stop`/`SubagentStop` with
`--stop`. Blocks only on lint keys `(code, message)` whose count grew against the
file's committed baseline; format drift is fed back as `additionalContext`.
Per-edit runs skip mid-edit codes (the `skip` list, e.g. `F401`, `F821`);
`--stop` and any `git commit` check every code. Prefers the project's uv-locked
`ruff`, else host `ruff`; needs `jq` and `git`. **Exception path:** the
end-of-turn report fires once - fix the findings, or keep them deliberately and
the turn ends on the re-entry.

## Trying a hook in isolation

Each hook reads a JSON event payload on stdin. Example for the bloat gate:

```sh
echo '{"tool_name":"Write","tool_input":{"file_path":"/tmp/scratch.md","content":"We should leverage this approach."}}' \
  | python3 ~/.claude/hooks/docs-bloat-gate.py
echo "exit code: $?"   # slop is advisory now: exit 0 + a JSON additionalContext
                       # nudge on stdout (write allowed). Only the opt-in S1 size
                       # ratchet exits 2 (blocked); its reason goes to stderr.
```

## Automated tests

Hook behaviour is pinned by a pytest suite in `tests/` (run `pytest` from the
repo root). `tests/test_impag_budget_check.py` covers the budget governor:
the exact tail-reader, the hard-stop and soft-band thresholds, the boundary
below the lowest band, the compaction regression, and fail-open. Add cases there rather than scripting throwaway checks.
