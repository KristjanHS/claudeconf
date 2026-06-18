---
name: finishing-a-development-branch
description: Close out a stage or branch — verify tests, report branch state, hand back to user (no merge/push).
---

# Finishing a Development Branch

## The Process

### Step 1: Verify Tests

**If a caller (`impag` Step 4c/Step 7, `subagent-driven-development` Step 7, `executing-plans` Step 5) already ran the full suite green this turn, skip and report `Tests: <X> passed (caller-run)`.** Re-running is a duplicate.

Otherwise run the project's test suite (`pytest tests/ -q`, `npm test`, `cargo test ./...`, etc.).

**If tests fail:** Stop. Report failures concisely and do not continue. The caller resolves.

**If tests pass:** Continue.

### Step 2: Report Branch State

```
Branch: <current-branch>
Commits ahead of <base>: <N> (<short-sha>..<short-sha>)
Tests: <X> passed
```

### Step 3: Return control silently

After Step 2's branch-state report, return control to the caller **in the same turn**. Do NOT print a discard reminder, a transition sentence ("Proceeding to /retro", "continuing", "now invoking the next step"), or any other callout. The caller advances directly to its next step in the same response — the handoff is silent by design. If the user wants to discard, they can type `discard` on a later turn and the caller routes to Step 4.

### Step 4: If the User Says `discard`

On explicit `discard`, confirm before acting:

```
Discard will permanently remove:
<commit-list>
Worktree: <path or "—">

Type `discard` again to confirm.
```

On the second `discard`, run the appropriate rollback:
- Local-only commits on an integration branch: `git reset --hard <base-SHA>`.
- Topic branch: `git checkout <base>` + `git branch -D <branch>` + worktree removal if present.

Otherwise do nothing.
