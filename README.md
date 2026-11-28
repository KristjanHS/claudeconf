# claudeconf

My Claude Code setup for long sessions, in pieces you can copy.

[![Secret scan](https://github.com/KristjanHS/claudeconf/actions/workflows/gitleaks.yml/badge.svg)](https://github.com/KristjanHS/claudeconf/actions/workflows/gitleaks.yml)
[![Tests](https://github.com/KristjanHS/claudeconf/actions/workflows/tests.yml/badge.svg)](https://github.com/KristjanHS/claudeconf/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[System](docs/system.md) · [Catalog](docs/catalog.md) · [Adopt](ADOPT.md)

![Statusline filling toward the session's token budget](docs/statusline.gif)

Long Claude Code sessions get slow and expensive, and when the context window fills up, Claude compacts
it into a summary. Anything that only existed in the conversation is lost at that point.

I use this config to push that moment back. Rules stay out of the prompt until Claude touches a file
they apply to. Hooks catch destructive commands and bloated docs. A separate reviewer agent reads every
finished change, and a budget hook tells a long run to wrap up before the window overflows.

It assumes you already use Claude Code. Nothing installs itself, so you copy what you want into
`~/.claude/` by hand. [docs/system.md](docs/system.md) shows how the pieces connect and the mistakes behind
each one.

## Quick start

Start with the statusline from the GIF. It shows how much of the session's token budget you've used,
and needs `bash`, `jq` and `git`. The statusline is 23 lines of bash, short enough to read before you run it;
[`tests/test_statusline.py`](tests/test_statusline.py) pins its claims (no network, no writes, no escapes from data).

```sh
git clone https://github.com/KristjanHS/claudeconf
cp claudeconf/.claude/statusline.sh ~/.claude/statusline.sh
chmod +x ~/.claude/statusline.sh
```

Then add the `statusLine` entry to `~/.claude/settings.json`:

```json
"statusLine": { "type": "command", "command": "~/.claude/statusline.sh", "padding": 0 }
```

If the line comes up blank, or you want different thresholds, see
[ADOPT.md §4](ADOPT.md#4-statusline).

The statusline only shows the number. The [budget governor](#the-budget-governor) acts on it, and it's
one file plus a `settings.json` entry ([ADOPT.md §3](ADOPT.md#3-runtime-hooks)).

## What's in it

| Group | What it does |
|---|---|
| Rules | Topic rules that load only when you touch a matching file, so `CLAUDE.md` stays small |
| References | Long checklists Claude reads only when `CLAUDE.md` points it there |
| Hooks | Snapshot before compaction and restore after it; block destructive shell commands; keep slow tests out of the default suite; hold the lint count |
| Review loop | A `code-reviewer` agent that reviews each finished change in a fresh context, plus model pins for the built-in agents |
| Skills | Context cleanup (`condense`, `de-bloat`), a plan executor (`impag`), debugging, testing, design and critique |
| Budget | A hook that tells a long run to wrap up, a bloat check on Markdown writes, and the statusline |

[docs/catalog.md](docs/catalog.md) lists every piece with how it works and what it costs.

## What's measured

Of this repo's files, only `CLAUDE.md` and the one-line skill descriptions load on every turn. Rules and references load when a matching file or pointer
fires. The table is generated from the repo, and `make test` fails when it goes stale.

<!-- context-cost:start -->
| Metric | Value |
|---|---|
| Always loaded: `CLAUDE.md` | 2,872 bytes (~718 tokens) |
| Path-gated rules | 9 |
| References | 23 |
| On demand: rules + references | 241,155 bytes |
| Statusline budget window | 300,000 tokens |
| Budget soft bands | 120,000 / 150,000 / 175,000 tokens |
| Budget hard stop | 200,000 tokens |
| Skills | 26 |
| Hooks | 12 |

Regenerate: `python3 scripts/context_cost.py --readme README.md`
<!-- context-cost:end -->

## Costs and limits

- Every Bash call runs six hooks (four before, two after). Each took 26–54 ms across four runs of
  [`scripts/time-hooks.sh`](scripts/time-hooks.sh), mostly interpreter startup.
  Internal errors exit 0, except in the destructive-command gate, which blocks a command it can't parse.
- Setup is manual: 152 lines of hooks config to merge into `settings.json`, and a pytest suite
  to keep up.
- The bloat check warns when a Markdown write adds slop phrases, thin text or a new audit doc.
  Dense writing that's fine can still trip it. In a project with `docs/spec.md` or `.claude/rules/`
  it also blocks oversized edits and Bash writes to those docs, unless overridden.
- At its hard stop the budget hook tells Claude to wrap up, ready or not. Raise `HARD_STOP_TOKENS` or
  drop the hook if your tasks need more.
- If your sessions stay under 120k tokens, the budget hook never fires.

## The budget governor

After each commit (and after any Bash call once the transcript is large), `impag-budget-check.py` reads
the exact token count from the transcript. Below the first soft band it says nothing. Each soft band
gets a one-line FYI, and the hard stop injects an instruction to this effect:

```
WRAP UP: do not start a new task. Finish what's in flight, save any remaining
tasks to project state, then review the code and close the branch, and record
the retro as owed for the next session rather than running it at this context.
```

When it has fired, Claude committed what it was working on, wrote the leftover tasks to a notes file
and stopped, so the next session picked up from a commit. More in
[.claude/hooks/README.md](.claude/hooks/README.md).

## How it was built

I built this repo with Claude Code, running written plans a stage at a time and handing each stage's
commits to a fresh reviewer. Some of what the agent got wrong was in the checks themselves, like a leak
gate that printed "no leakage" and exited 0 when git failed ([`2ad3e5a`](https://github.com/KristjanHS/claudeconf/commit/2ad3e5a))
and a doc-link checker that missed slug and code-fence cases ([`d2f6c14`](https://github.com/KristjanHS/claudeconf/commit/d2f6c14)).
Review caught both, and [docs/system.md](docs/system.md) walks through that loop.

## Built with it

- [transcribe-offline](https://github.com/KristjanHS/transcribe-offline) (51 tests, 11 releases)
- [my-vector](https://github.com/KristjanHS/my-vector), a wire-pod fork (609 tests added)
- [stt-faster](https://github.com/KristjanHS/stt-faster) (388 tests, 10 releases)

Tests are a static count of `def test_` and `func Test` at HEAD, and releases are `v*` tags, both
counted by [`scripts/agentic_stats.py`](scripts/agentic_stats.py).

## Tests

`make test` runs shellcheck and ruff, the pytest suite, a private-path scan, a drift check of the
synced files against the source repo, and a staleness check on the measured-cost table. The drift
check skips when the source repo isn't on disk. CI runs pytest on pushes to `main` and on pull
requests, and gitleaks on every push and pull request.

MIT licensed. Written by [Kristjan](https://github.com/KristjanHS).
