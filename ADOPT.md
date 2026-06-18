# Adopting the pieces

This is the **"I'm convinced, now how do I adopt it"** path — the why for each
piece (and where it isn't worth it) lives in the [README](README.md). Copy-in,
by hand, one piece at a time. **Back up anything you overwrite**, and **never
blind-overwrite your own `~/.claude/settings.json`** — merge the hooks block
instead. Everything below assumes your config lives at `~/.claude/`.

Most steps end with a **smoke-test**: it confirms the piece is *wired and fires*,
not that it improved your session. (The value question is the README's job.)

## 1. The progressive-disclosure `CLAUDE.md`

`.claude/CLAUDE.md` is an **example skeleton**, not a config to copy verbatim.
Adopt the *structure*, not the contents:

- A **"References (read when triggered)"** section — point at L3 docs that load
  only when a trigger fires.
- A path-gated **"Rules Index"** table — one row per rule file, so the rule
  body stays out of context until a matching file is touched.

Merge that structure into your existing `CLAUDE.md`; fill the rows with your own
rules.

## 2. Path-gated rules

```sh
cp .claude/rules/*.md ~/.claude/rules/
```

Each rule's frontmatter `globs` is the gating mechanism — it auto-loads only
when a matching file is read/edited. Keep the frontmatter. The four shipped
rules are good as-is, but tune them to your stack. List each in your
`CLAUDE.md` Rules Index table.

**Smoke-test:** confirm the file is in `~/.claude/rules/` with its `globs`
frontmatter intact — that frontmatter is what the harness keys the gating on.
There's no context-inspector to *watch* a rule load; the only observable effect
is behavioral (Claude following the rule once you touch a matching file), which
proves wiring, not that the rule changed an outcome.

## 3. Runtime hooks + `settings.json` wiring

```sh
cp .claude/hooks/*.py ~/.claude/hooks/
chmod +x ~/.claude/hooks/*.py
```

Then **merge** (do not overwrite) the hook entries from `.claude/settings.json`
into your own `~/.claude/settings.json`. The shipped file shows exactly the
five hooks wired:

- `PreCompact` → `pre-compact.py`
- `SessionStart` → `post-compact-restore.py` (on compact/resume) and
  `session-start-health.py` (on startup)
- `PreToolUse` (Write/Edit/Bash) → `docs-bloat-gate.py`
- `PostToolUse` (Bash) → `impag-budget-check.py`

If you keep separate `settings.json` files, add the matchers to whichever one
already holds your hooks. Confirm Claude Code reports no settings errors after.

How the budget governor measures context (exact, compaction-aware, zero-dep) and
why it shares the statusline's 130k mark is documented once in
**[`.claude/hooks/README.md`](.claude/hooks/README.md#the-budget-governor--impag-budget-checkpy)** — read it there.

**Smoke-test (hooks):** run a hook against a synthetic stdin payload and check
its exit code — the bloat-gate example is in the
[hooks README](.claude/hooks/README.md#trying-a-hook-in-isolation). A non-error
exit (or exit 2 = blocked, for the gate) confirms it's installed and runs.

## 4. Statusline

```sh
cp .claude/statusline.sh ~/.claude/statusline.sh
chmod +x ~/.claude/statusline.sh
```

Point `statusLine` at it in `settings.json` (see the shipped example). It needs
only `jq` and `git`. Note the context window is pinned to a personal 200k
budget with a 130k/160k yellow/red mark — the same 130k the budget governor
wraps up on. `WINDOW` is the token budget you choose to treat as your personal
session cap (here 200k) — deliberately *below* the model's real context limit
(e.g. 1M), so the bar fills and warns well before any native autocompact. Set it
to whatever cap you want to pace yourself against; adjust the thresholds to match.

**Smoke-test:** start a session and confirm the status line renders (context %,
cost, distance-to-stop). If it's blank, check `jq`/`git` are on `PATH` and the
`statusLine` path in `settings.json` is correct.

## 5. Skills

```sh
cp -r .claude/skills/* ~/.claude/skills/
```

`condense`, `de-bloat`, and `claude-md-progressive-disclosurer` are the
context-hygiene trio; `impag` showcases the parallel-subagent fan-out.
`detect-ai-text-humanize` is the odd one out: it flags AI-sounding prose and
rewrites it to read human, with a detection mode (full report) and a
humanization mode (rewrite only). Point it at a doc with "humanize the AI text
in X" or "check X for AI". They are self-contained, and any reference to tooling
you don't run is written as optional.

**Smoke-test:** type `/` in a session and confirm the copied skills appear in
the slash-command list (or invoke `/<name>` and watch it load). That proves
they're discoverable; whether a skill helps is a per-task judgement.

## 6. The secret gate (reuse in your own repos)

For **this** repo: `./install.sh` points git at `hooks/` (pre-commit +
pre-push). To reuse the gate in another repo, copy `hooks/`, `scripts/`,
`.gitleaksignore`, and `.github/workflows/gitleaks.yml`, then run the same
`git config core.hooksPath hooks`. Install [gitleaks](https://github.com/gitleaks/gitleaks#installing)
for the credential scan (the hooks warn and skip gracefully without it). The
PII check blocks any `/home/<user>/` path or email in tracked files — widen or
relax the patterns in `scripts/check-hardcoded-paths.sh` for your needs.
