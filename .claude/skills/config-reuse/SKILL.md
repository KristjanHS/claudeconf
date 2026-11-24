---
name: config-reuse
description: Copy/sync Claude configs, rules, Makefile targets & git hooks from other projects.
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

### 2. Scan Source

No `SOURCE_PATH` given → run `bash ~/.claude/skills/config-reuse/scripts/rank-sources.sh "$(pwd)"` and offer its top 3 rows.

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

**Linked — never copy:**
- `stack_linked` → add the target to `PY_PROJECTS` (the item to `PY_LINKS` if absent) in `~/projects/dotfiles/scripts/link-stack-config.sh`, then run it.
- `broken_link` → run `link-stack-config.sh` if it lists the item (it relinks); else route it as a source-side follow-up (step 9).

### 5. Present and Copy

Show a table of recommendations grouped by action. Wait for approval.

Copy approved configs:
- **Commands** → `~/.claude/commands/` (global)
- **Skills** → `.claude/skills/` (project) or `~/.claude/skills/` (global, if general)
- **Rules** → `.claude/rules/` (project)
- Back up before overwriting: `cp <existing> ~/.claude/backups/<name>.bak.$(date +%s)`
- If a skill has a project name in `description:`, edit it after copying
- Adapt on copy: drop source-project names, paths and incidents, and any line contradicting `~/.claude/CLAUDE.md` (e.g. plan dir must be `docs/plans/archive/`).
- **Claim-check adapted rules:** list every technical claim each adapted rule makes (commands, paths, flags, behaviour), then dispatch `Agent(subagent_type="code-reviewer")` to check that list against the target before committing.

### 6. Make Targets

- **Python → start from the template:** `cp -rn ~/.claude/skills/config-reuse/assets/python/. .` (every existing file is kept — merge by hand: `pyproject.toml` `[tool.*]` tables, `Makefile` via `diff-make-targets.sh`), set `name`, then delete each target whose subject is absent.
- **Shared targets:** the target's `Makefile` ends with `-include $(HOME)/.config/make/worktree.mk` (`syncwt`/`commit`/`commitwt`); `help` stays the first target so it is the default goal.
- **`check` target is mandatory** — `~/bin/syncwt` auto-detects `^check:` (else `^test:`) as its land gate.
- **Stack targets:** `bash ~/.claude/skills/config-reuse/scripts/diff-make-targets.sh <src> .` prints the source-only targets with recipes, paste-ready (`--names` for the list).
- Adopt only targets whose tool config exists in the target (no `.pre-commit-config.yaml` → no `pre-commit`/`yamlfmt`; no `scripts/git-hooks` → no `setup-hooks`); drop variant/GPU/torch plumbing.
- **Falsifier:** plant a type error and an unused import under the source dir, confirm `make check` exits non-zero, delete them; `make commit <a-target-name>` must refuse.

### 7. Hook Targets (suggest, then implement on approval)

- Recon first: `bash ~/.claude/skills/config-reuse/scripts/diff-hooks.sh <src> .` — `global` rows (e.g. a global push-policy hook) survive any per-repo install, never re-implement them; a `repo` row is not inherited — offer it, don't assume it.
- Claude Code hooks (`~/.claude/settings.json`: `ruff-check.sh`, `pyright-check.sh`) are a session-feedback layer, not a commit gate — keep both; confirm they bind here (ruff in `uv.lock`, `[tool.pyright]` + `.venv`) by piping `{"tool_input":{"file_path":"<planted.py>"}}` into the hook.
- Python → keep the template's `.pre-commit-config.yaml`, then delete each hook whose subject is absent; custom git-hooks dirs + `core.hooksPath` only for repos with CI/Docker scale.
- Adopt a hook only when its subject exists in the target: ruff/ruff-format (Python), check-yaml (YAML config), actionlint (`.github/workflows/`), hadolint (own Dockerfile), deptry (non-trivial deps).
- Pin remote revs with `pre-commit autoupdate --repo <url>`.
- `pre-commit run --all-files` sees tracked files only — commit the config before trusting a `Skipped`. Run `uv add` outside make (`UV_LOCKED` is exported only inside it).
- Verify: `git hook list pre-push` shows the global hook next to `hook from hookdir`; planted commit/push defects → step 8's `verify-target.sh`.
- **Promote to global** (in a dotfiles session): add `[hook "<name>-commit"]` to `git/.gitconfig` + its script under `git/.config/git/hooks/`, then list each project's now-duplicate id from `bash ~/.claude/skills/config-reuse/scripts/find-dup-hooks.sh` for removal — never edit other projects in-session.

### 8. Verify the Environment

- Run `bash ~/.claude/skills/config-reuse/scripts/verify-target.sh <repo>` (fresh-clone target matrix + planted commit/push defects); paste its table into the report — any FAIL row is unfinished work.
- `*wt` targets halting with "no linked worktrees" is the expected result in a repo without worktrees.
- Missing system tools (Blender, Docker) → report the install command; never install system packages unasked.

### 9. Route Source-Side Follow-ups

- Source-side findings (`broken_link` rows, divergent variants of one config) go to a `<source>/docs/plans/` file or a handoff line in the report.
- Never fix a multi-file source-side issue from the target session — a single-file one-off is the only exception.

## Safety

- Never copy `settings.local.json` or files matching `*secret*`, `*credential*`
- Back up before overwriting
