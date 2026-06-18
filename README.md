# claudeconf

A small, **copy-in catalog** of the Claude Code tricks that keep a session's
context window lean — custom `CLAUDE.md` structure, path-gated rules,
continuity hooks, a budget governor, and a portable statusline. Each piece
ships with a short "why it saves context" note, so it's a teaching artifact as
much as a drop-in.

It is **not** an installer. Nothing here auto-merges into your config. You copy
the pieces you want into your own `~/.claude/`, by hand, and adapt them. The
only script is a one-liner that activates this repo's git **secret gate**.

> Assumes you already use Claude Code and are comfortable editing your own
> `~/.claude/` and merging a `settings.json` hooks block by hand.

## Two `hooks/` directories — don't conflate them

| Directory | What it is | Goes where |
|---|---|---|
| **`.claude/hooks/`** | Claude Code **runtime** hooks (the teaching content: context continuity, anti-bloat, budget governor) | your `~/.claude/hooks/` |
| **`hooks/`** (repo root) | **git** hooks (the secret gate: gitleaks + PII check) | activated in *this* clone via `./install.sh` |

## What's inside, and why each piece saves context

### The context-optimization mechanisms (the heart of the repo)

1. **Progressive-disclosure `CLAUDE.md`** (`.claude/CLAUDE.md`) — a "References
   (read when triggered)" section + a path-gated "Rules Index" table. The
   single biggest saver: rule text loads only when matching files are touched,
   instead of sitting in every prompt. Paired with the
   `claude-md-progressive-disclosurer` skill.
2. **Path-gated rules** (`.claude/rules/*.md` with frontmatter `globs`) —
   auto-load only when relevant files are read/edited. Four exemplars ship,
   including `instruction-file-discipline.md` (the L1/L2/L3 tiering that keeps
   instructions in the right file).
3. **Context-continuity hooks** — `pre-compact.py`, `post-compact-restore.py`,
   `session-start-health.py`: preserve and restore state across a compaction so
   context survives a compact without re-derivation.
4. **Anti-bloat hook** — `docs-bloat-gate.py`: blocks oversized / low-density
   docs from entering context in the first place. Self-contained (its
   docs-quality helpers are inlined).
5. **Budget governor** — `impag-budget-check.py`: a PostToolUse hook that makes
   long `/impag` runs stop taking new work before the context cliff. Reads the
   **exact, compaction-aware** context size by parsing the last assistant turn's
   reported `usage` from the transcript tail — zero dependencies (see below).
6. **Statusline** — `statusline.sh`: live context %, distance-to-stop, cost, and
   5h-limit. Needs only `jq` + `git`; ships unchanged.

The budget governor and the statusline **share the same 130k mark _and_ the same
measurement** (yellow at 130k, red at 160k): both sum
`input_tokens + cache_creation_input_tokens + cache_read_input_tokens`, so the
*visual* warning and the *automated* wrap-up fire off the same number, not just
the same threshold.

### Flagship skills (`.claude/skills/`)

The context-hygiene trio — `condense`, `de-bloat`,
`claude-md-progressive-disclosurer` — plus `impag` as a showcase of the
parallel-subagent fan-out pattern.

### The secret gate

A three-layer check that no secret or personal identity ships:

| Layer | What runs | When |
|---|---|---|
| `hooks/pre-commit` | gitleaks (staged) **+** blocking identity/PII check | every commit |
| `hooks/pre-push` | full working-tree gitleaks scan | every push |
| `.github/workflows/gitleaks.yml` | gitleaks on push + PR | server-side (un-bypassable) |

The PII check (`scripts/check-hardcoded-paths.sh`) is **blocking** here (it is
advisory in the source dotfiles): a public teaching repo has no legitimate
reason to ship a home path or an email. It uses **generic** patterns
(`/home/<user>/`, any email) rather than any hardcoded identity.

## Quick start

```sh
git clone https://github.com/KristjanHS/claudeconf
cd claudeconf
./install.sh            # optional: activate the git secret gate for this clone
```

Then see **[ADOPT.md](ADOPT.md)** for how to copy each piece into your own
`~/.claude/`. The full rationale (every decision and rejected alternative) is in
[`docs/2026-06-18-claudeconf-design.md`](docs/2026-06-18-claudeconf-design.md).
