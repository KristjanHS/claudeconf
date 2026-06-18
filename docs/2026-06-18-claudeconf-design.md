# claudeconf — Design

**Date:** 2026-06-18
**Status:** Approved design, pre-build
**Repo:** https://github.com/KristjanHS/claudeconf (public)

## Goal

A public, shareable repo that helps co-workers **adopt the Claude Code
context-optimization tricks** developed in the author's private dotfiles —
custom skills, hooks, rules, statusline, and the config patterns that keep a
session's context window lean. It is both a **drop-in catalog** (co-workers
copy what they want into their own `~/.claude`) and a **teaching artifact**
(each piece ships with a short "why it saves context" writeup).

A hard requirement: the repo enforces an **automated secret-check before
commit and before push**, reusing the gitleaks-based checking logic from the
source dotfiles repo.

## Audience

Co-workers already using Claude Code who want to copy proven configs rather
than design their own. They are assumed to be comfortable editing their own
`~/.claude/` and merging a `settings.json` hooks block by hand.

## Sources

- `~/projects/dotfiles/claude/.claude/` — skills, hooks, rules, references,
  `CLAUDE.md`, `settings.json`, `statusline.sh` (primary source)
- `~/projects/dotfiles/hooks/` + `scripts/check-hardcoded-paths.sh` — the
  secret/hygiene gate logic to reuse
- `~/projects/stt-faster/` — a *consumer* project; source for the
  `.claudeignore` and project-rule examples

## Chosen approach

**Full-mirror structure, curated content, copy-in adoption.**

- **Structure** mirrors a real `.claude/` tree so co-workers can drop pieces
  straight into their own setup (rejected: a flat "reference dump" that
  wouldn't map onto a live config).
- **Content** is hand-curated to the high-value context tricks, not a full
  copy of all 25 skills / 9 hooks (rejected: full mirror of everything — too
  noisy for adopters).
- **Adoption** is copy-in (a documented catalog), not an auto-installer that
  merges `settings.json` (rejected: auto-merge is the single most likely
  thing to break a co-worker's existing config). The only script is a
  one-liner to activate the git secret-hooks.

## Repository structure

```
claudeconf/
├── README.md                  # the pitch + index + "why each trick saves context"
├── ADOPT.md                   # copy-in instructions, per piece
├── docs/
│   └── 2026-06-18-claudeconf-design.md   # this document
├── .claude/                   # drop-in shaped; co-workers copy what they want
│   ├── CLAUDE.md              # sanitized example: progressive-disclosure skeleton
│   ├── settings.json          # sanitized: shows the curated hooks wiring only
│   ├── statusline.sh          # context %/cost/limit status line (portable)
│   ├── rules/                 # 3 exemplar path-gated rules + instruction-file-discipline
│   ├── hooks/
│   │   ├── README.md
│   │   ├── pre-compact.py
│   │   ├── post-compact-restore.py
│   │   ├── session-start-health.py
│   │   ├── docs-bloat-gate.py
│   │   └── impag-budget-check.py   # PORTABLE variant (no token_monitor dep)
│   └── skills/                # 3-4 flagship, sanitized
│       ├── condense/
│       ├── de-bloat/
│       ├── claude-md-progressive-disclosurer/
│       └── impag/             # showcase of the subagent-fanout pattern
├── hooks/                     # the SECRET GATE (git hooks; core.hooksPath target)
│   ├── pre-commit             # gitleaks --staged + BLOCKING identity/path check
│   └── pre-push               # full working-tree gitleaks scan
├── scripts/
│   ├── check-hardcoded-paths.sh   # adapted from dotfiles; BLOCKING in this repo
│   └── hardcoded-paths-allowlist.txt
├── .gitleaksignore
├── .github/workflows/gitleaks.yml # server-side backstop (push + PR)
└── install.sh                 # one optional step: git config core.hooksPath hooks
```

### Two `hooks/` directories — intentional

- `.claude/hooks/` = **Claude Code runtime hooks** (the teaching content —
  context continuity, anti-bloat, budget governor).
- root `hooks/` = **git hooks** (the secret gate).

The README explains this distinction up front so co-workers don't conflate
them.

## Curated content and the "why"

### Context-optimization mechanisms (the heart of the repo)

1. **Progressive-disclosure `CLAUDE.md`** — the "References (read when
   triggered)" + path-gated "Rules Index" pattern. The single biggest
   context saver: rules load only when matching files are touched, instead of
   sitting in every prompt. Paired with the `claude-md-progressive-disclosurer`
   skill.
2. **Path-gated rules** (`rules/*.md` with frontmatter globs) — auto-load only
   when relevant files are read/edited. Paired with
   `instruction-file-discipline.md` (the L1/L2/L3 tiering).
3. **`.claudeignore`** — keeps files out of context entirely.
4. **Context-continuity hooks** — `pre-compact.py`,
   `post-compact-restore.py`, `session-start-health.py`: preserve and restore
   state across compaction so context survives a compact without re-derivation.
5. **Anti-bloat hook** — `docs-bloat-gate.py`: blocks oversized docs from
   entering context.
6. **Budget governor** — `impag-budget-check.py` + `statusline.sh` (see below).
7. **Statusline** — `statusline.sh`: live context %, distance-to-stop, cost,
   5h limit. Fully portable (`jq`+`git`, reads Claude Code's statusline JSON).
8. **`settings.json`** — sanitized, shows how the curated hooks are wired.

### Flagship skills (examples, not the full set)

`condense`, `de-bloat`, `claude-md-progressive-disclosurer` (the
context-hygiene trio), plus `impag` as a showcase of the parallel-subagent
fan-out pattern.

## The budget governor (detailed — the `/impag` early wrap-up)

`impag-budget-check.py` is a **PostToolUse hook on `Bash`** that makes
`/impag` stop taking new work before the session hits its context cliff:

1. **Triggers** — primary: a `git commit` (the natural `/impag` task
   boundary). Fallback: any Bash call once a cheap `transcript_bytes / 4`
   proxy crosses ~100k, so a working-tree-only session that never commits is
   still caught.
2. **Measures** current context usage from the transcript.
3. **Hard-stop at 130k tokens** — silent below that by design; at ≥130k it
   injects (via the `additionalContext` JSON envelope — plain stdout would
   only reach the Ctrl-R transcript, not Claude's context) a wrap-up
   reminder: *finish in-flight work, save remaining tasks to project state,
   then run code review → finishing-a-development-branch → retro.*
4. **Fail-open** — any error exits 0; never blocks a commit.

The **130k threshold is shared with `statusline.sh`** (yellow at 130k, red at
160k), so a co-worker gets the *visual* warning and the *automated* wrap-up
off the same mark — they are taught together.

### Portability decision (key)

The author's real hook imports `token_monitor.parser.parse_last_turn`, a
**private editable install** (`~/projects/token-monitor`, not on PyPI). Copied
as-is it raises `ModuleNotFoundError`.

**Resolution:** ship a **self-contained portable variant** that uses the
`transcript_bytes / 4` estimator for the actual token count too — no external
import, slightly less accurate, teaches the identical pattern. The accurate
`token_monitor`-backed version is documented as an optional upgrade; the
private package is **not** vendored.

By contrast, `statusline.sh` has **no** such dependency and ships unchanged.

## The secret gate (reused dotfiles logic, hardened for public)

Three layers:

| Layer | What runs | When |
|---|---|---|
| `hooks/pre-commit` | `gitleaks git --pre-commit --staged` (graceful warn if gitleaks absent) **+** blocking identity/path check on staged files | every commit |
| `hooks/pre-push` | full working-tree `gitleaks` scan | every push |
| `.github/workflows/gitleaks.yml` | gitleaks on push + PR | server-side (can't be `--no-verify`'d) |

- **Activation:** `install.sh` runs `git config core.hooksPath hooks` (the one
  command co-workers run after cloning).
- **`.gitleaksignore`** documents any false positives.

### One deliberate change from dotfiles

In dotfiles, `check-hardcoded-paths.sh` is **advisory** (`exit 0`, never
blocks) because dotfiles legitimately pins some `/home/kristjans/` paths. In a
public teaching repo there is **no legitimate reason** for a home path or
email to ship, so the check is **blocking (`exit 1`)** in pre-commit and the
pattern is widened to catch `/home/kristjans/`, `kristjan.h.s@gmail.com`, and
bare-username references. gitleaks catches *credentials*; this catches
*identity/PII leakage*, which is the dominant risk for this repo.

## Sanitization (one-time pass before first commit)

Every curated file is scrubbed before it lands:

- **Paths** — `/home/kristjans/...` → `$HOME/...` or `~/...`
- **Identity** — email/username removed from `CLAUDE.md`, `settings.json`,
  statusline examples
- **Private project refs** — drop `stt-faster` / `straiker` / devcontainer /
  WSL-specific incident text; rewrite skill bodies that name private memory
  slugs to generic placeholders
- **Dependency** — `token_monitor` import swapped for the portable `bytes/4`
  variant
- **`settings.json`** — trimmed to just the curated hooks block; no
  marketplace / plugin / personal paths

The blocking path-check is the safety net that *proves* the sanitization pass
worked: if anything personal slips through, the first commit fails.

## Key decisions

1. **Full-mirror structure + curated content** — drop-in shape, but only the
   high-value tricks (not all 25 skills / 9 hooks).
2. **Copy-in adoption, not auto-install** — avoids clobbering a co-worker's
   `settings.json`. Only script is the secret-hook activator.
3. **Portable budget-hook variant** — `bytes/4`, no private `token_monitor`
   dependency; accurate version documented as optional.
4. **Path/identity check is blocking here** (advisory in dotfiles) — PII
   leakage is the real risk for a public repo.
5. **CI gitleaks backstop** — server-side, un-bypassable, because it's public.

## Out of scope

- Auto-merging `settings.json` into a co-worker's existing config.
- Vendoring or publishing the private `token-monitor` package.
- The full set of personal skills/hooks/rules (kaizen suite, forensic
  tooling, devcontainer/WSL specifics, memory internals).
- Any push to the remote — commits are local; the author pushes from the WSL
  host per their git-push policy.

## Build plan (next session/turn)

1. Scaffold the structure above in `~/projects/claudeconf`.
2. Curate + sanitize each file from source.
3. Write the portable `impag-budget-check.py` variant.
4. Wire the secret gate (`hooks/`, `scripts/`, `.gitleaksignore`, CI, `install.sh`).
5. Write `README.md` + `ADOPT.md`.
6. Verify: run gitleaks + the blocking path-check over the tree; confirm clean.
7. Commit locally; hand back to author to push from host.
