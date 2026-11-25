# claudeconf

My Claude Code setup for long sessions, split into pieces you can copy.

[![Secret scan](https://github.com/KristjanHS/claudeconf/actions/workflows/gitleaks.yml/badge.svg)](https://github.com/KristjanHS/claudeconf/actions/workflows/gitleaks.yml)
[![Tests](https://github.com/KristjanHS/claudeconf/actions/workflows/tests.yml/badge.svg)](https://github.com/KristjanHS/claudeconf/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[System](docs/system.md) · [Why](docs/why.md) · [Catalog](docs/catalog.md) · [Adopt](ADOPT.md) · [Quick start](#quick-start)

![Statusline filling toward the session's token budget](docs/statusline.gif)

Long Claude Code sessions get slow and expensive, and when the context window fills up, Claude compacts
it into a summary. Anything that only existed in the conversation is lost at that point.

I use this config to push that moment back. Rules stay out of the prompt until Claude touches a file
they apply to. Hooks catch destructive commands and bloated docs. A separate reviewer agent reads every
finished change, and a budget hook tells a long run to wrap up before the window overflows.

It assumes you already use Claude Code. Nothing installs itself, so you copy what you want into
`~/.claude/` by hand. [docs/system.md](docs/system.md) shows how the pieces connect and
[docs/why.md](docs/why.md) has the mistakes behind each one.

## Quick start

Start with the statusline from the GIF. It shows how much of the session's token budget you've used,
and needs `bash`, `jq` and `git`.

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
[docs/statusline_adopt.md](docs/statusline_adopt.md). [ADOPT.md](ADOPT.md) covers everything else.

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

Only `CLAUDE.md` is loaded on every turn. Rules and references load when a matching file or pointer
fires. The table is generated from the repo, and `make test` fails when it goes stale.

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

- Every Bash call runs four hooks. The Python ones took 25–40 ms each in a local timing, most of it
  interpreter startup. They fail open, so a hook error never blocks you.
- Setup is manual: about 125 lines of hooks config to merge into `settings.json`, and a pytest suite
  to keep up.
- The bloat check sometimes flags dense writing that's fine. It only warns, except for the opt-in size
  ratchet, which blocks but can be overridden.
- The budget hook stops you at its hard stop, ready or not. Raise `HARD_STOP_TOKENS` or drop the hook
  if your tasks need more.
- If your sessions are short, skip all of this.

## The budget governor

After each Bash call, `impag-budget-check.py` reads the exact token count from the transcript. Below the
first soft band it says nothing. Each soft band gets a one-line FYI, and the hard stop injects this:

```
WRAP UP: do not start a new task. Finish what's in flight, save any remaining
tasks to project state, then review the code and close the branch - and record
the retro as owed for the next session rather than running it at this context.
```

When it has fired, Claude committed what it was working on, wrote the leftover tasks to a notes file
and stopped, so the next session picked up from a commit. More in
[.claude/hooks/README.md](.claude/hooks/README.md).

## Built with it

- [transcribe-offline](https://github.com/KristjanHS/transcribe-offline) (48 tests, 10 releases)
- [my-vector](https://github.com/KristjanHS/my-vector), a wire-pod fork (576 tests added)
- [stt-faster](https://github.com/KristjanHS/stt-faster) (387 tests, 10 releases)

MIT licensed. Written by [Kristjan](https://github.com/KristjanHS).
