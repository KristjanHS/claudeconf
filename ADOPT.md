# Adopting the pieces

Back up anything you are about to overwrite, and merge `settings.json` by hand rather than copying it over
yours. Go in step order; [docs/catalog.md](docs/catalog.md) says what each piece does.

Everything below assumes your config lives at `~/.claude/`. A smoke test only proves a piece is wired and
fires, not that it made your sessions better.

## 1. The `CLAUDE.md` skeleton

Don't copy `.claude/CLAUDE.md` as is; it's there to show the shape. Two sections are worth taking:
References, which points at long docs Claude reads only when a trigger fires, and the Rules Index, with
one row per rule file. Then fill them with your own rules.

## 2. Path-gated rules

```sh
cp .claude/rules/*.md ~/.claude/rules/
```

Keep the `paths:` frontmatter; a rule loads only when Claude reads or edits a matching file, and that
block is the whole mechanism. Tune the rules to your stack. List each in your Rules Index.

Smoke test: check the `paths:` block survived the copy.

## 3. Runtime hooks

```sh
cp .claude/hooks/*.py .claude/hooks/*.sh ~/.claude/hooks/
chmod +x ~/.claude/hooks/*.py ~/.claude/hooks/*.sh
mkdir -p ~/.claude/lib && cp .claude/lib/ask_paths.py ~/.claude/lib/
```

Then merge the hooks block from `.claude/settings.json` into your `~/.claude/settings.json` and check that
Claude Code reports no settings errors. Dependencies:

- `destructive-bash-gate.py` needs `~/.claude/lib/ask_paths.py` for its ask-path check.
- `agent-model-pin-gate.py` checks against the agent pins: `cp .claude/agents/*.md ~/.claude/agents/`.
- `ruff-check.sh` needs `ruff`, `jq` and `git`; `pyright-check.sh` needs `pyright` and `jq`.
- `upstream-exec-gate.py` loads `fetch-quarantine-gate.py`, which loads `destructive-bash-gate.py`; keep all
  three in one dir, or both gates silently allow everything. `upstream-exec-gate.py`'s per-project
  config is `.claude/upstream-exec.json`, described in the [hooks README](.claude/hooks/README.md#upstream-exec-gatepy).
- `fetch-quarantine-gate.py` does nothing until you list trusted trees, one absolute path per line (`~` is not expanded):
  `mkdir -p ~/.claude/safe-hashes && echo "$HOME/projects" >> ~/.claude/safe-hashes/trusted-dirs.txt`.
  Put the helpers it points to on your `PATH`: `cp bin/bin/* ~/bin/` (keep them in one dir).
- `session-start-health.py` warns at startup when `CLAUDE_SAFE=1` is unset outside a container. That flag
  comes from the author's launcher, which isn't published; export it yourself or drop that check.

Smoke test: pipe a sample payload into a hook, as in the
[hooks README](.claude/hooks/README.md#trying-a-hook-in-isolation). Exit 0 means it is installed and runs.

## 4. Statusline

Install it as in the README's [quick start](README.md#quick-start). `WINDOW` sits below the model's real
limit so the bar warns before native autocompact. The other four are fixed token counts that don't move
with it, so edit them together:

| Line | Default | Controls |
|---|---|---|
| `WINDOW=300000` | 300k | 100% of the bar and the % shown |
| `STOP=225000` | 225k | the stop point the warning counts down to |
| `AMBER=200000` | 200k | bar turns yellow |
| `RED=240000` | 240k | bar turns red |
| `WARN=30000` | 195k | `← /clear soon` appears, 30k before the stop |

If you run the budget governor (`impag-budget-check.py`), keep its 200k hard stop equal to the yellow mark.

Smoke test: open a new session. The status line should show model, bar, %, tokens, folder and branch,
followed by the 5-hour and 7-day limits. If it stays blank, `jq` or `git` is missing from `PATH`, or the
`statusLine` path in `settings.json` points at the wrong file.

## 5. Skills

```sh
cp -r .claude/skills/* ~/.claude/skills/
cp .claude/references/*.md ~/.claude/references/
```

Several skills read files from `~/.claude/references/`, so copy the references along with them.
[docs/catalog.md](docs/catalog.md#skills) lists every skill. The `kaizen-*` skills work as a set.
`ext-repo-safety` needs the `bin/bin/` helpers on your `PATH` (step 3).

Smoke test: type `/` in a session and look for the copied skills in the list.
