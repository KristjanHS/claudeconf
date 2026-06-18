# Adopting the pieces

Copy-in, by hand, one piece at a time. **Back up anything you overwrite**, and
**never blind-overwrite your own `~/.claude/settings.json`** — merge the hooks
block instead. Everything below assumes your config lives at `~/.claude/`.

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

### Budget governor: the portable vs. accurate variant

`impag-budget-check.py` ships as a **portable `bytes/4`** estimator with **no
external dependency** — it works on any machine immediately, just slightly less
accurate. If you have a real per-turn token counter, swap it into
`estimate_tokens()` and keep everything else; the rest of the hook is unchanged.
The accurate version is the only "upgrade" — no private package is vendored.

## 4. Statusline

```sh
cp .claude/statusline.sh ~/.claude/statusline.sh
chmod +x ~/.claude/statusline.sh
```

Point `statusLine` at it in `settings.json` (see the shipped example). It needs
only `jq` and `git`. Note the context window is pinned to a personal 200k
budget with a 130k/160k yellow/red mark — the same 130k the budget governor
wraps up on. Adjust `WINDOW` / thresholds to taste.

## 5. Skills

```sh
cp -r .claude/skills/* ~/.claude/skills/
```

`condense`, `de-bloat`, and `claude-md-progressive-disclosurer` are the
context-hygiene trio; `impag` showcases the parallel-subagent fan-out. They are
self-contained — any reference to tooling you don't run is written as optional.

## 6. The secret gate (reuse in your own repos)

For **this** repo: `./install.sh` points git at `hooks/` (pre-commit +
pre-push). To reuse the gate in another repo, copy `hooks/`, `scripts/`,
`.gitleaksignore`, and `.github/workflows/gitleaks.yml`, then run the same
`git config core.hooksPath hooks`. Install [gitleaks](https://github.com/gitleaks/gitleaks#installing)
for the credential scan (the hooks warn and skip gracefully without it). The
PII check blocks any `/home/<user>/` path or email in tracked files — widen or
relax the patterns in `scripts/check-hardcoded-paths.sh` for your needs.
