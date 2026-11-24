# Skill & File Management SOP

## Backup & Collision

Back up files before removing or editing skills — use `~/.claude/backups/` (outside the skills directory so backups aren't loaded). When installing a skill whose name collides with an existing one, flag the conflict and ask the user for a unique name — don't silently replace.

## Global Skills Live Globally — No Project Copies

Global skills belong in `~/.claude/skills/<name>/`, version-controlled via the dotfiles backup only (`~/projects/dotfiles/skills/<name>/`, sym/hard-linked to the live file — **one inode, not a fork**). **Never copy a global skill into an individual project's `.claude/skills/`** — that spawns a divergent duplicate that rots out of sync. A project's `.claude/` carries only project-specific rules/skills, never a copy of a global one. The dotfiles backup repo is the sole exception (it *is* the global store under version control); it is not a "project copy." If you find a project-level copy of a global skill, flag it for removal **from that project's own session** (cross-project-edit discipline).

## Syncing Skills to Dotfiles

Skills in `~/.claude/skills/` should be symlinked to `~/projects/dotfiles/skills/` for backup. The pattern:
1. Copy skill to `dotfiles/skills/<name>/`
2. Replace original with symlink: `ln -s ../../../projects/dotfiles/skills/<name>/SKILL.md`

Skills installed via `/install-skill` or manually are plain files — they won't be backed up until symlinked. Periodically compare `ls ~/.claude/skills/` vs `ls ~/projects/dotfiles/skills/` to catch drift. Also remove dotfiles entries for uninstalled skills.

**`npx skills-installer install` needs a raw TTY** — in the Claude Code harness it dies at the confirm prompt (`TTY initialization failed: uv_tty_init returned EINVAL`); there is no `--yes`/non-interactive flag. Install manually instead: `curl` the raw `SKILL.md` (+ any supporting files the SKILL.md references, e.g. `EXAMPLES.md`/`TEMPLATES.md`) from `raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>/` straight into `dotfiles/skills/<name>/`, then `ln -s` the live symlink. Note `sync-skills.sh add <name>` requires the **live** `~/.claude/skills/<name>` dir to already exist (it moves live→dotfiles); when seeding dotfiles-first, create the symlink by hand — the end state (`SYMLINKED` per `sync-skills.sh status`) is identical.

## Source Precedence When Multiple Copies Exist

When a skill exists in more than one source, resolve by this precedence:

1. **Dotfiles version wins.** The user's dotfiles copy carries accumulated security + style hardening and should not be re-bloated back to upstream shape during migration, optimization, or sync.
2. **Plugin cache** — treat as the live upstream; relied on when no dotfiles copy exists. For `superpowers-dev`, this is `~/.claude/plugins/cache/superpowers-dev/superpowers/<version>/`.

`~/projects/claude_skills/superpowers/` is **not a precedence source** — it's a marketplace shell (`.claude-plugin/{marketplace,plugin}.json` only) registered in `extraKnownMarketplaces` and bind-mounted into the devcontainer. It does not contain runnable skills. Never edit anything under there expecting Claude Code to pick it up.

Never auto-merge an "upstream-fresher" copy over a dotfiles version without the user's explicit cherry-pick decision.

## Pre-Edit Landscape Check

Before editing any skill, run a landscape pass:

1. **Canonical path** — `ls -la <skill-dir>` to see if it's a symlink and where its source lives (dotfiles vs. plain dir vs. plugin cache). Edit the canonical path, not the symlink.
2. **Callers** — `grep -r <skill-name>` across `~/.claude/skills/` and active plugin caches under `~/.claude/plugins/cache/` to find who dispatches it. Preserve their expected output contract. Sweeping references across the *whole* stowed `~/.claude/` tree (e.g. retiring a shared path): `grep -r ~/.claude` skips stow's file-symlinks during recursion and **false-passes** — use `find -L ~/.claude -name '*.md' | xargs grep -l <pattern>` to follow symlinks, or grep the canonical `dotfiles/claude/.claude/` source directly. Retiring a path cited from a **project repo** too: don't filter the sweep to `*.md` — script/config headers (`.sh`, `.json`, Makefiles) cite doc paths and a `.md`-only grep false-passes on those live citations.
3. **Git-tracked status** — if the canonical path isn't git-tracked (e.g., `~/.claude/skills/<name>/` plain dir), promote into dotfiles first so edits are durable.

Skipping this pass leads to mid-design surprises about contracts, cross-project ownership, or lost edits.

## Integrate Every Edit — No Contradictions Left Behind

An instruction edit (skill, rule, reference, or CLAUDE.md) is not done when the new text is written — it's done when the **surrounding instructions still agree with it**. Whenever you add, change, or remove a step/rule/constraint:

1. **Sweep the neighbours** — the other steps in the same file; any step that references numbering or ranges ("Steps 2–4", "Step 3 short-circuit"); silence/close/scope notes that enumerate which steps they cover; and **every other file that names the changed behaviour** (`grep` the *concept*, not just the skill name).
2. **Update them in the same burst** so none now contradicts, double-counts, or dangles: a new step a sibling's short-circuit would silently skip, a renamed target a downstream list still omits, a numbering reference that no longer spans the steps, a duplicated home for one fact.
3. **A partial edit that leaves a contradiction is a defect**, not a smaller version of the change. Prefer one integrated edit over several that each need reconciling later.

Applies to `reflect` proposals, `retro`'s rule/doc writes, `de-bloat`, `condense`, and any hand edit to an instruction file.

## Extending Shared Skills

When extending shared skills or docs, propose the single highest-impact change rather than multiple moderate additions.

## Cross-Skill Link Discipline

Before adding a `Related Skills` link, a `See <skill-name>` pointer, or any reference that names another skill, verify the target skill exists in `~/.claude/skills/` (or in the active plugin cache). Broken cross-skill links rot silently — they don't error at load time, and a future reader following the link wastes a turn discovering it's gone. If the target was vendored from upstream and never installed locally, drop the link entirely rather than leaving the dangling reference as a placeholder.

## Post-Install: Promote + Vendor-Strip

Applies to every install path (`install-skill`, `skills-discovery`, manual `curl`).

**Promote to shared — always, without asking.** A fresh install lands as a real directory at `~/.claude/skills/<name>/` (`LOCAL` per `sync-skills.sh status`); LOCAL skills are per-machine and not backed up. Run `~/projects/dotfiles/scripts/sync-skills.sh add <name>`, then commit the new skill dir. Skip only if the user explicitly asks to keep it local.

**Install one, question one.** Name any existing skill the install makes redundant (or state none) and propose its removal.

**Vendor-strip the SKILL.md before promoting.** These frontmatter fields are read by nothing in Claude Code and pad always-loaded tokens: `tokenEstimate`, `agents`, `trust_tier`, `validation`, `implementation_status`, `optimization_version`, `last_optimized`, `quick_reference_card`, `category`, `priority`, `dependencies`. Drop each unless `grep` shows a hook or script consuming it. Trim `tags` to ≤3; keep `name` + `description`. Cut an opening "Quick Reference Card", "Three Modes" table, or "Related Skills" block whose targets don't exist locally. Rewrite `description:` to one-line trigger language ≤120 chars (`recording-principles.md` § Description field) — it loads into EVERY session. Delete sibling files the body never references (CHANGELOGs, READMEs, test fixtures, schemas, example assets).

## Post-Install Description Review

After installing a skill, review its `description` frontmatter. "Proactively invoke" language causes mid-session auto-activation on matched triggers (e.g. user corrections). If the skill should only run on explicit invocation, narrow the description to name the trigger (e.g. *"Invoke ONLY when the user runs `/X` or calls this skill from step N of skill Y"*) — body unchanged.

## One-Command Tools → `bin/`, Not Skills

A skill costs ~85 always-loaded tokens for its `description` frontmatter (loaded every session so the model can route to it). A one-command tool that needs no model-routing — a wrapper, an alias, a fixed action invoked by name — should be a `bin/` script instead: zero always-loaded cost. Reach for a skill only when the model must *decide* to invoke it. Precedent: `bin/bin/winsleep` (host-sleep wrapper) is a script, not a skill.

