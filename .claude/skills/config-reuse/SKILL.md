---
name: config-reuse
description: Copy/sync Claude configs & rules from another project.
---

# Config Reuse

Import Claude Code configs (commands, skills, rules) from a source project into the current project or global config.

## Workflow

### 1. Detect Target Stack

Check current project for language indicators:

```bash
# Python?
[[ -f pyproject.toml ]] || [[ -f setup.py ]] || [[ -f requirements.txt ]] && echo python
# TypeScript?
[[ -f tsconfig.json ]] && echo typescript
# JavaScript?
[[ -f package.json ]] && echo javascript
# Rust?
[[ -f Cargo.toml ]] && echo rust
# Go?
[[ -f go.mod ]] && echo go
```

Save detected languages as `TARGET_LANGS`. On a fresh repo with no manifests yet, take the stack from the args or the project's plan doc.

No `SOURCE_PATH` given → pick sources by stack: list `~/projects/*/.claude/` with py/Makefile/Dockerfile/.gitmodules markers, and diff the 2–4 closest.

### 2. Scan Source

```bash
bash ~/.claude/skills/config-reuse/scripts/scan-configs.sh "$SOURCE_PATH"
```

Output: TSV with TYPE, REL_PATH, MD5, MARKERS per config file.

### 3. Compare

```bash
bash ~/.claude/skills/config-reuse/scripts/diff-configs.sh "$SOURCE_PATH" "$(pwd)"
```

Output: TSV with TYPE, REL_PATH, STATUS, MATCH_PATH.

### 4. Classify

Using script outputs + target stack:

**Skip:**
- `CLAUDE.local.md`, `.claudeignore` (always project-specific)
- Configs with `DOMAIN:*` markers (domain-specific)
- `identical_global` or `identical_project` status (already installed)
- Language-marked configs where language is NOT in `TARGET_LANGS`

**Auto-recommend:**
- `not_installed` configs with no `DOMAIN:*` markers AND (no language markers OR language in `TARGET_LANGS`)

**Needs judgment — read the file:**
- `differs_global` or `differs_project` status (merge decision)
- Root `CLAUDE.md` or `.claude/CLAUDE.md` (may have extractable sections)
- Rules with `paths:` frontmatter (check if glob matches target project)

### 5. Present and Copy

Show a table of recommendations grouped by action. Wait for approval.

Copy approved configs:
- **Commands** → `~/.claude/commands/` (global)
- **Skills** → `.claude/skills/` (project) or `~/.claude/skills/` (global, if general)
- **Rules** → `.claude/rules/` (project)
- Back up before overwriting: `cp <existing> ~/.claude/backups/<name>.bak.$(date +%s)`
- If a skill has a project name in `description:`, edit it after copying
- **Stack-linked items** (a source symlink into `~/projects/dotfiles`, e.g. `python-refactors.md`, `python-simplifier`) → add the project to its `*_PROJECTS` array in `dotfiles/scripts/link-stack-config.sh` and run the script; never copy.
- Adapt on copy: drop source-project names, paths and incidents, and any line contradicting `~/.claude/CLAUDE.md` (e.g. plan dir must be `docs/plans/archive/`).

### 6. Make Targets

- **Shared targets:** the target's `Makefile` ends with `-include $(HOME)/.config/make/worktree.mk` (`syncwt`/`commit`/`commitwt`); `help` stays the first target so it is the default goal.
- **`check` target is mandatory** — `~/bin/syncwt` auto-detects `^check:` (else `^test:`) as its land gate.
- **Stack targets:** harvest recipes from the source Makefiles:
  `awk '/^(sync|unit|test|lint|fmt|pyright|ruff-[a-z]+|audit|check|pre-commit|semgrep|deptry)[[:space:]]*:/{f=1;print;next} f&&/^\t/{print;next} {f=0}' <src>/Makefile`
- Adopt only targets whose tool config exists in the target (no `.pre-commit-config.yaml` → no `pre-commit`/`yamlfmt`; no `scripts/git-hooks` → no `setup-hooks`); drop variant/GPU/torch plumbing.
- **Python baseline:** `sync` (`uv sync --locked --all-groups` + `uv pip check`), `lint` (`ruff check`, `ruff format --check`, `pyright`), `fmt`, `test`, `audit` (`uv audit`); `check` = `git diff --check 4b825dc642cb6eb9a060e54bf8d69288fbee4904 -- . ':!*.md'` (empty tree — syncwt gates a clean tree, so `HEAD` can never fail) + lint + test. Tools go in the uv `dev` group, not `uvx`.
- Python Makefile guards: `export UV_LOCKED := 1` (a stale lock fails instead of being rewritten mid-gate); `pytest … || [ $$? -eq 5 ]` (no tests collected ≠ failure).
- No parse-time `$(shell …)` in a Makefile that includes `worktree.mk` — its stderr poisons the `make commit` message-guard probe.
- Ruff `extend-exclude` (never `exclude`) must list vendored dirs and `"**/*.md"` — ruff ≥0.16 formats Python blocks inside Markdown, i.e. docs and rules.
- **Falsifier:** plant a type error and an unused import under the source dir, confirm `make check` exits non-zero, delete them; `make commit <a-target-name>` must refuse.

### 7. Hook Targets (suggest, then implement on approval)

- Recon first: `git config --show-origin --get-regexp '^hook\.'` + `--get-all core.hooksPath` — global config-based hooks (e.g. a global push-policy hook) survive any per-repo install; never re-implement them per repo.
- A `core.hooksPath` with origin `file:.git/config` (e.g. dotfiles' gitleaks) is that repo's own, not global — the target does not inherit it; offer it, don't assume it.
- Claude Code hooks (`~/.claude/settings.json`: `ruff-check.sh`, `pyright-check.sh`) are a session-feedback layer, not a commit gate — keep both; confirm they bind here (ruff in `uv.lock`, `[tool.pyright]` + `.venv`) by piping `{"tool_input":{"file_path":"<planted.py>"}}` into the hook.
- Prefer the pre-commit framework: `setup-hooks` = `uv run pre-commit install --hook-type pre-commit --hook-type pre-push`, `pre-commit` = `run --all-files`; the sources' custom `scripts/git-hooks/` + `core.hooksPath` is only for repos with CI/Docker scale.
- Adopt a hook only when its subject exists in the target: ruff/ruff-format (Python), check-yaml (YAML config), actionlint (`.github/workflows/`), hadolint (own Dockerfile), deptry (non-trivial deps).
- Repos with private/binary inputs (PDF, images, `.blend`) always get `check-added-large-files` — `.gitignore` covers known dirs only. Pre-push stage = `make check`.
- Ruff hooks are `repo: local`, `language: system`, `entry: uv run --locked ruff … --force-exclude` — the lock-pinned ruff, so hook and `make lint` never drift; pin remote revs with `pre-commit autoupdate --repo <url>`.
- `pre-commit run --all-files` sees tracked files only — commit the config before trusting a `Skipped`. Run `uv add` outside make (`UV_LOCKED` is exported only inside it).
- Verify: `git hook list pre-push` shows the global hook next to `hook from hookdir`; in the fresh clone, a >500 KB file and an F401 must be refused at commit, and committed whitespace must fail `pre-commit run --hook-stage pre-push`.

### 8. Verify the Environment

- Fresh-clone matrix: `git clone -q . <scratchpad>/clone`, run every non-mutating target there (`help sync check fmt audit test`); each must exit 0 with nothing new in `git status`.
- Each gate component owes a demonstrated failure in the clone: committed trailing whitespace, a failing test, a stale lock (dep added to `pyproject.toml` → `make lint` non-zero, `uv.lock` untouched).
- `*wt` targets halting with "no linked worktrees" is the expected result in a repo without worktrees.
- Missing system tools (Blender, Docker) → report the install command; never install system packages unasked.

## Safety

- Never copy `settings.local.json` or files matching `*secret*`, `*credential*`
- Back up before overwriting
