# claudeconf

Claude Code config for long sessions: lean context, guard hooks and a token budget.

[![Secret scan](https://github.com/KristjanHS/claudeconf/actions/workflows/gitleaks.yml/badge.svg)](https://github.com/KristjanHS/claudeconf/actions/workflows/gitleaks.yml)
[![Tests](https://github.com/KristjanHS/claudeconf/actions/workflows/tests.yml/badge.svg)](https://github.com/KristjanHS/claudeconf/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[System](docs/system.md) · [Why](docs/why.md) · [Catalog](docs/catalog.md) · [Adopt](ADOPT.md) · [Quick start](#quick-start)

![Statusline filling toward the session's token budget](docs/statusline.gif)

Long Claude Code sessions get slow and expensive. Once the context window fills, Claude compacts it to a
summary, and reasoning that lived only in the conversation is gone. This is the config I use to put that
off: rules stay out of the prompt until a matching file is touched, hooks flag or block bad output, a
separate reviewer agent checks each finished change, and a budget hook stops a run before it overflows.

It's for people who already use Claude Code. Nothing installs itself; you copy the pieces you want into
`~/.claude/`. [docs/system.md](docs/system.md) shows how they fit together, and
[docs/why.md](docs/why.md) has the mistakes that led to each one.

## Quick start

The statusline in the GIF shows how much of the session's token budget is used. It needs `bash`, `jq`
and `git`.

```sh
git clone https://github.com/KristjanHS/claudeconf
cp claudeconf/.claude/statusline.sh ~/.claude/statusline.sh
chmod +x ~/.claude/statusline.sh
```

Then add this to `~/.claude/settings.json`:

```json
"statusLine": { "type": "command", "command": "~/.claude/statusline.sh", "padding": 0 }
```

Thresholds and troubleshooting are in [docs/statusline_adopt.md](docs/statusline_adopt.md). For the rest
of the kit, see [ADOPT.md](ADOPT.md).

## What's in it

| Group | What it does |
|---|---|
| Rules | Topic rules that load only when you touch a matching file, so `CLAUDE.md` stays small |
| References | Long checklists Claude reads only when `CLAUDE.md` points it there |
| Hooks | Snapshot before compaction and restore after it; block destructive shell commands; keep slow tests out of the default suite; hold the lint count |
| Review loop | A `code-reviewer` agent that reviews each finished change in a fresh context, plus model pins for the built-in agents |
| Skills | Context cleanup (`condense`, `de-bloat`), a plan executor (`impag`), debugging, testing, design and critique |
| Budget | A hook that tells a long run to wrap up, a bloat check on Markdown writes, and the statusline |

Every piece, with how it works and what it costs, is in [docs/catalog.md](docs/catalog.md).

## What's measured

Only `CLAUDE.md` is loaded on every turn. Rules and references load when a matching file or pointer
fires. `make test` fails if this table no longer matches the repo.

<!-- context-cost:start -->
| Metric | Value |
|---|---|
| Always loaded: `CLAUDE.md` | 5,006 bytes (~1,251 tokens) |
| Path-gated rules | 9 |
| References | 14 |
| On demand: rules + references | 154,737 bytes |
| Statusline budget window | 300,000 tokens |
| Budget soft bands | 120,000 / 150,000 / 175,000 tokens |
| Budget hard stop | 200,000 tokens |
| Skills | 28 |
| Hooks | 7 |

<sub>Regenerate: `python3 scripts/context_cost.py --readme README.md`</sub>
<!-- context-cost:end -->

## Costs and limits

- Four hooks run on every Bash call. Each Python hook took 25–40 ms per call when timed locally, mostly
  interpreter startup. All of them fail open: an error exits 0 and never blocks you.
- Setup is by hand. The hooks block in `settings.json` is about 125 lines to merge, and you maintain the
  pytest suite yourself.
- The bloat check can flag dense writing that is fine. Its slop, density and new-file signals only warn;
  the opt-in size ratchet is the one that blocks, and it can be overridden.
- The budget hook interrupts at its hard stop whether you're ready or not. If a task needs more, raise
  `HARD_STOP_TOKENS` or leave the hook out.
- None of this pays off in short sessions. It assumes sessions long enough for context to be the bottleneck.

## The budget governor

`impag-budget-check.py` reads the exact token count from the transcript after each Bash call. It stays
quiet below the first soft band, posts a one-line FYI at each soft band, and at the hard stop it injects:

```
WRAP UP: do not start a new task. Finish what's in flight, save any remaining
tasks to project state, then review the code and close the branch - and record
the retro as owed for the next session rather than running it at this context.
```

In the runs where it fired, Claude committed the task in flight, wrote the leftover work to a notes file
and stopped. The next session started from committed state, not from a compaction summary. Details are
in [.claude/hooks/README.md](.claude/hooks/README.md).

## Built with it

- [transcribe-offline](https://github.com/KristjanHS/transcribe-offline): 48 tests, 10 releases
- [my-vector](https://github.com/KristjanHS/my-vector): a wire-pod fork, 576 tests added
- [stt-faster](https://github.com/KristjanHS/stt-faster): 387 tests, 10 releases

MIT licensed. By [Kristjan](https://github.com/KristjanHS).
