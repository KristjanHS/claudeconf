# Plan: dotfiles → claudeconf sync, and the statusline GIF regen

Status: **open** — Stages 1–4 done (claudeconf `eb51692..HEAD`, dotfiles `102ee3f`,`ad21282`); next Stage 5 · Created 2026-09-26 · Rulings: user, 2026-09-26 (binding, restated below)

Run from a **claudeconf-cwd session** (`/qimpag`). Touches three repos: claudeconf (stages 1–4, 7),
`../dotfiles` (1.1, 5), `../ai-coding-journey` (6). Each commits in place on its checked-out branch
(`main`), pathspec'd (`git commit -m … -- <paths>`); **never push** — the user pushes.

## Rulings (2026-09-26)

- **Manifest + proposals.** Tracked `sync-manifest.txt` maps claudeconf path ← dotfiles path. `make sync`
  also PRINTS dotfiles-only files (not in manifest, not in `sync-ignore.txt`); never auto-publishes them.
- **Never synced:** `.claude/CLAUDE.md`, `.claude/settings.json` — teaching skeletons. No symlinks.
- **Sanitize + blocking gate.** Home paths rewritten; the PII gate + gitleaks run after sync and fail
  loudly; a private name sanitize can't fix → that file is **refused**, not published.
- **Permanence.** Idempotent `make sync`; a dotfiles post-commit hook runs it into claudeconf's working
  tree (never commits/pushes, always exit 0); `make check` gains a drift check that skips without dotfiles.
- Every new gate owes a **mutate-and-confirm-red** demo before its slice is called verified.
- **D1:** private terms = the private app repo + employer prefix (+ user adds); `ai-coding-journey` is nameable, not a term.
- **D2:** a held (refused) file **warns** — `--check` prints `HELD <path>` and exits 0; the stale copy stays.
- **D3 (re-ruled at Stage 7):** `.claude/lib/docs_quality.py` is NOT published — no importer after D6's fork; in `sync-ignore.txt`.
- **D4:** a dir mirror adds + updates, **never deletes**; claudeconf-only extras (21 in 5 skill dirs) are not drift.
- **D5:** `sync-ignore.txt` = the personal set only (models, devcontainer, persistence, symlinks, syncwt/wimpag, forensic hooks).
- **D6 (3.1):** forks = `hooks/README.md`, `docs-bloat-gate.py`, `condense/`, `de-bloat/`; private-app incident details and personal-workflow lines publish as-is.

## Recon (2026-09-26)

- **Everything differs.** All 16 core files (statusline.sh, 4 hooks + hooks/README.md, 4 rules, 7 refs)
  and all 22 name-matched skill dirs differ between claudeconf and dotfiles; 5 claudeconf skills have no
  dotfiles counterpart (stay unsynced, unlisted).
- **Sanitize hits in dotfiles sources of the candidate manifest: 26 across 7 files.**
  - Home paths: `/home/<user>/` **0**; `/Users/<user>/` **1** (an upstream example in
    `skills/systematic-debugging/root-cause-tracing.md`). Emails **0**.
  - Private names **25 in 6 files**: private app repo ×17, journey repo ×3 (nameable per D1 — not refused), employer-prefixed project ×5
    (in `anti-patterns-common-rationalizations.md`, `subagent-dispatch.md`, `pre-ship-sweeps.md`,
    `rules/claude-md-edits.md`, `hooks/docs-bloat-gate.py`, `hooks/README.md`).
  - Advisory: 23 lines in 10 files cite `dotfiles` / `~/projects/…` (dangling in a public clone, not PII).
- **Sed alone is not enough**: the 25 name hits are prose cites of private plans. Without per-term rewrites,
  6 of the 16 core files are refused (see 3.1).
- **Dependency:** dotfiles `hooks/docs-bloat-gate.py` imports `.claude/lib/docs_quality.py` (claudeconf has
  no `lib/`) → the manifest adds it (D3).
- **Behaviour change on sync:** dotfiles `statusline.sh` pins `WINDOW=300000` (yellow ≥200k, red ≥240k,
  7d segment, worktree-primary `PROJ`); dotfiles `HARD_STOP_TOKENS = 200_000` vs claudeconf's `130_000`.
  `tests/test_impag_budget_check.py` (8 literal hits), README.md and ADOPT.md prose all assume 130k/160k/200k.
- **Gate gap:** `check-hardcoded-paths.sh` scans the **index** (`git grep --cached`) — a fresh sync is
  unstaged, so the gate as written cannot see it.
- dotfiles installs hooks via `core.hooksPath hooks` (`bootstrap.sh`); `hooks/` holds pre-commit, pre-push;
  `tests/hooks.bats` copies a hook into a throwaway repo. Its stow list is `PACKAGES` (explicit).
- GIF: `FRAMES` are sized for the 200k statusline (red at 168k); under the 300k script that frame is green.
- ai-coding-journey backlog: the row **and** the `**Next:**` line both cite the regen.

## Design

- **Engine:** `scripts/sync_from_dotfiles.py` (stdlib, ruff + pytest already gate `scripts/`, `tests/`).
  Modes: default = sync; `--check` = drift; `--dry-run` = report, write nothing. `DOTFILES` env overrides the `../dotfiles` default.
- **Source = dotfiles `HEAD`** (`git show` / `git ls-tree`), never its working tree: uncommitted WIP and
  untracked `__pycache__` can never publish, and the post-commit hook syncs exactly what was committed.
- **Manifest:** one `<claudeconf path> <- <dotfiles path>` per line; trailing `/` = directory mirror
  (adds + updates, never deletes — D4). `NEVER_SYNC` constant refuses CLAUDE.md/settings.json even if listed.
- **Private data stays private:** the term list and rewrite rules name private repos, so they live in
  dotfiles `claudeconf-publish/{private-terms.txt,rewrites.tsv}` (top-level, not in `PACKAGES` → not stowed).
  Missing term list → **fail closed** (refuse all), never open.
- **`sanitize(text, suffix)`**, deterministic: (1) ordered `rewrites.tsv` regexes; (2) `/home/<u>/`,
  `/Users/<u>/` → `~/` (md/other) or `$HOME/` (.sh); .py hit → refuse; (3) any remaining gate pattern,
  email or private term (case-insensitive, word-bounded) → refuse the file, print term + line.
- **Proposals:** `PROPOSAL_ROOTS` = dotfiles `claude/.claude/{hooks,rules,references,lib,agents,commands}`,
  `statusline.sh`, `skills/*`; print each unlisted, un-ignored path as `not published — add to manifest?`.
- **Advisory dangling cites:** print synced files citing a `references/`/`rules/` name not in the manifest.
- **Exit codes:** sync 0 = clean; 1 = any refusal or post-sync gate hit (other files still written).
  `--check` 0 = in sync, skipped, or only held files (printed `HELD`, D2); 1 = drift.
- Manifest targets are dotfiles-owned: a hand edit in claudeconf is overwritten by the next sync (drift
  check flags it first).

## Refactor-first assessment

- **`check-hardcoded-paths.sh` is index-only** → add a `--worktree` mode (`git grep --untracked`) with the
  same patterns/allowlist before anything depends on it (slice 2.1). Default stays `--cached` for pre-commit.
- `make_statusline_gif.py` `FRAMES` tuple grows a column; hoist a `RED_FRAME` constant + assertion rather
  than a comment (4.1). Nothing else warrants a refactor.

## Stage 1 — Sync engine, manifest, sanitize

### 1.1 Engine + manifest + private seed

- **Focus:** `scripts/sync_from_dotfiles.py`, `sync-manifest.txt`, `sync-ignore.txt`,
  `tests/test_sync_from_dotfiles.py`; dotfiles `claudeconf-publish/private-terms.txt` (seed: every private
  sibling repo name found in recon except `ai-coding-journey` + employer prefix, per D1), empty `rewrites.tsv`.
- Manifest = 16 core files + 22 skill dirs (`lib/docs_quality.py` dropped at Stage 7, D3). `sync-ignore.txt` = dotfiles-only
  files judged personal (e.g. models, devcontainer, persistence refs); it must pass the PII gate itself.
- Tests use a tmp git repo as fake dotfiles (CI has none): rewrite per suffix, refusal, fail-closed,
  dir-mirror keeps extras (D4), NEVER_SYNC, idempotence (2nd run = 0 changed), HEAD-not-worktree.
- **Verify:** `make test-lint && make test-pytest`; `time python3 scripts/sync_from_dotfiles.py --dry-run`
  (record wall time — it sets the 5.1 hook mode).
- **Falsifiers:** drop the `.py` refusal branch → its test goes red; point terms at a missing file →
  sync must exit 1 with every file refused.
- **Commit:** claudeconf (engine, manifest, ignore, tests); dotfiles `-- claudeconf-publish/`.

## Stage 2 — Gates

### 2.1 PII + gitleaks after sync

- **Focus:** `scripts/check-hardcoded-paths.sh` (`--worktree`), `Makefile` (`sync:` = engine →
  `check-hardcoded-paths.sh --worktree` → `gitleaks dir` over synced targets; missing gitleaks = warn,
  matching `hooks/pre-commit`).
- **Verify:** `make sync` on a clean tree exits 0; `make test-paths` unchanged.
- **Red demo:** plant a home path (`/home/` + any user + `/x`) in an untracked `.claude/rules/zz.md` → `--worktree` exits 1 while
  plain `make test-paths` (index) stays 0 — proves the new mode sees what the old could not. Remove.

### 2.2 Drift check

- **Focus:** `Makefile` — `test-drift` (engine `--check`) joins `test`; add `check: test` alias; renumber
  the `[n/4]` labels; help text.
- **Verify:** `make check` green; `DOTFILES=/nonexistent make test-drift` → exit 0 + `drift: skipped`.
- **Red demo:** append a line to a synced `.claude/rules/testing.md` → `make test-drift` exits 1 naming
  it; `git checkout` it → green.
- **Commit:** claudeconf `-- Makefile scripts/ tests/`.

## Stage 3 — First real sync

### 3.1 Rewrites, sync, review

- Author `rewrites.tsv` for the 25 name hits: full private-path cites first
  (`~/projects/<private>/…` → `a private project's plan`), bare names after. Review every rewritten line.
- `make sync`; `git diff --stat`, then read each file's diff. Any claudeconf copy that is an intentional
  teaching fork → move its line from manifest to a `# fork` note in `sync-ignore.txt`, restore the file.
- Still-held files print `HELD` and keep their stale copy (D2); add a rewrite or de-manifest each one in 3.1.
- **Verify:** `make sync` twice (2nd prints 0 changed); `make check`.
- **Falsifier:** delete one `rewrites.tsv` row → `make sync` exits 1 naming that file; restore.

### 3.2 Fallout of the new numbers

- **Focus:** `tests/test_impag_budget_check.py` (import `HARD_STOP_TOKENS`, never a literal), README.md,
  ADOPT.md statusline/governor prose (300k window, 200k/240k marks, 200k governor, 7d segment).
- **Verify:** `make check`; `grep -nE '130k|160k' README.md ADOPT.md` → only deliberate history, if any.
- **Commit:** claudeconf `-- sync-manifest.txt sync-ignore.txt .claude/ tests/ README.md ADOPT.md`;
  dotfiles `-- claudeconf-publish/rewrites.tsv`.

## Stage 4 — GIF regen

### 4.1 seven_day + 300k frames

- **Focus:** `scripts/make_statusline_gif.py` — `FRAMES` gains a 7d column; payload adds
  `rate_limits.seven_day.used_percentage`; rescale for the 300k script: ≈27k, 83k, 147k, 186k,
  201k (yellow + `/clear soon`), 231k (hero), **252k = 84% red**. 7d = 14,15,17,18,19,21,22; model `Opus 5.5` (ruled).
- Add `RED_FRAME = 6`; `main()` asserts that frame's bar SGR is 31 and its text holds `84%`, and asserts
  every line's drawn width ≤ `W - PAD_X` (the 7d + repo segments lengthen it; widen `W` if needed).
- **Verify:** `python3 scripts/make_statusline_gif.py` → `docs/statusline.gif (7 frames)`; open frame 6
  (PIL `seek(6)`) and eyeball: red bar, `84%`, `7d:` segment visible, nothing clipped.
- **Red demo:** set frame 6 to 239k → the `RED_FRAME` assertion fails; restore.
- **Done note (fill in):** red frame index = `6` (0-based), tokens/percent = `252k / 84%`.

### 4.2 README stills

- Export `docs/statusline.png` (a green frame) and `docs/statusline2.png` (hero frame) from the same
  renderer so README stills match the GIF; README alt text/prose agree with the new numbers.
- **Verify:** `make check`. **Commit:** claudeconf `-- scripts/make_statusline_gif.py docs/ README.md`.

## Stage 5 — dotfiles post-commit hook (dotfiles tree)

### 5.1 Hook + bats

- **Focus:** dotfiles `hooks/post-commit`, `tests/post_commit.bats` (pattern of `tests/hooks.bats`).
- Behaviour: changed paths (`git diff-tree --no-commit-id --name-only -r HEAD`) outside `claude/.claude/`,
  `skills/`, `claudeconf-publish/` → no-op; skip mid-rebase; claudeconf dir = `CLAUDECONF_DIR` or
  `../claudeconf` — absent → silent no-op.
- Runs `timeout 10 make -s -C "$cc" sync`; failure prints one line + the manual command; **always exit 0**.
  If 1.1's timing > 2 s, background it instead, logging to `$XDG_STATE_HOME/claudeconf-sync.log`.
- bats cases (stub claudeconf Makefile touching a marker): sibling absent, unrelated path, manifest path,
  stub fails → exit 0 + message, stub hangs → timeout.
- **Verify:** dotfiles `make test-lint && make test-bats`.
- **Red demo:** remove the path filter → the unrelated-path case goes red; restore.
- **Commit:** dotfiles `-- hooks/post-commit tests/post_commit.bats`.

## Stage 6 — ai-coding-journey copy (journey tree)

### 6.1 GIF copy + backlog row

- `cp docs/statusline.gif ../ai-coding-journey/content/media/statusline.gif`.
- In `docs/plans/journey-backlog.md`: delete the "Regenerate `statusline.gif` before inc-deck2-slides" row
  and reword `**Next:**` to start at inc-deck2-slides; note red frame = `RED_FRAME` index for the deck still.
- **Verify:** in `../ai-coding-journey`, `make check` (never piped).
- **Commit:** `-- content/media/statusline.gif docs/plans/journey-backlog.md`.

## Stage 7 — Full verify, live e2e, review

- claudeconf `make check`; dotfiles `make test`; `git status --short` clean in all three repos.
- **Live e2e:** in dotfiles, append a comment line to `claude/.claude/rules/testing.md`, commit → claudeconf
  `git status --short` shows `.claude/rules/testing.md` with that line; `git revert --no-edit HEAD` in
  dotfiles → claudeconf file back to its committed state. Time both commits (target: no noticeable delay).
- **Code review:** fresh `code-reviewer` subagent over all three repos' stage commits; brief = this plan.
  Triage by defect class; fixes as their own pathspec'd commits; re-run `make check`.
- Close: status → closed, fill the 4.1 done note, `git mv` to `docs/plans/archive/`.

## Out of scope

- Publishing any dotfiles-only file — the user opts in by adding a manifest line later.
- Changing the `.claude/CLAUDE.md` / `.claude/settings.json` skeletons.
- Symlinks; auto-commit or auto-push of claudeconf (the hook only writes the working tree).
- Fixing dangling cites to unpublished refs (reported, not fixed); journey prose quoting the old 130k.
