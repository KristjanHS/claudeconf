# How the system works

A coding agent's output can look done when it isn't. Code passes the tests the agent wrote for itself, a
check reports green because it cannot fail, and a doc states a claim nobody re-checked. Docs also keep
growing until they crowd out the context the work needs.

Four layers answer that, drawn as the loop they form. What a session learns goes back into the rules.

```
  rules ──► gates ──► review loop ──► cost budget
    ▲                                      │
    └──────── /retro, /reflect ◄───────────┘
```

One choice runs through all of them: a check must be able to fail. Something that passes by
construction will read as proof forever, which is why every new check ships with a red demo where you
break the line it guards, watch it fail and put it back. No demo, no check.

## Rules: say what good looks like

`CLAUDE.md` loads on every turn ([size](../README.md#whats-measured)), so it keeps only the always-on rules and points
at the rest. A path-gated rule loads only when Claude touches a file matching its `paths:` frontmatter;
references load when a pointer sends Claude there.

Files: [`.claude/CLAUDE.md`](../.claude/CLAUDE.md), [`.claude/rules/`](../.claude/rules/),
[`.claude/references/`](../.claude/references/).

## Gates: flag or block the output that isn't

The bloat gate nudges on slop, thin text and new audit docs. Spec and rule files it blocks outright once they
grow past a size cap. Tests get five questions from the test rule before anyone writes them, and a test that
can't fail on a real bug doesn't get past. Leaks need their own guard. This repo's own pre-commit and pre-push hooks
and CI keep credentials, private paths and dead links out of the public tree.

A leak gate once read its own error as clean: a git failure printed "no leakage" and exited 0. Review
caught it, and it now fails closed
([`2ad3e5a`](https://github.com/KristjanHS/claudeconf/commit/2ad3e5a)).

Files: [`docs-bloat-gate.py`](../.claude/hooks/docs-bloat-gate.py),
[`rules/testing.md`](../.claude/rules/testing.md), [`hooks/pre-commit`](../hooks/pre-commit),
[`scripts/check-hardcoded-paths.sh`](../scripts/check-hardcoded-paths.sh).

## Review loop: catch what slips past the gates

The plan executor (`impag`) runs a plan a stage at a time. At each stage boundary it runs the full suite, then hands the
stage's commits to a fresh `code-reviewer` subagent, which reads the diff but not the reasoning behind it.
In the [dispatch benchmark](../.claude/references/subagent-dispatch.md#code-review-dispatch--evidence)
the bundled `/code-review` caught no more than that plain subagent, at ~14× the tokens.

Two trails, each plan → build → the review fix that corrected it:

- [my-vector](https://github.com/KristjanHS/my-vector), sealing the first real-use window.
  [Plan](plans/archive/2026-11-15-my-vector-prod-evidence.md), build
  [`da037e6`](https://github.com/KristjanHS/my-vector/commit/da037e6), fix
  [`20a7475`](https://github.com/KristjanHS/my-vector/commit/20a7475). The old month test never crossed
  a month; review caught a seal that a late restart could falsify.
- [transcribe-offline](https://github.com/KristjanHS/transcribe-offline), hardening an offline
  transcriber. [Plan](https://github.com/KristjanHS/transcribe-offline/blob/main/docs/plans/archive/2026-09-27-security-critique-todo.md),
  build [`1137856`](https://github.com/KristjanHS/transcribe-offline/commit/1137856), fix
  [`1deb918`](https://github.com/KristjanHS/transcribe-offline/commit/1deb918). When deleting a
  mismatched `uv.exe` failed, its post-check was skipped too, so an unverified `uv.exe` ran.

The doc-link checker caught a dead `ADOPT.md` anchor on its first run, and review then found slug and
code-fence gaps in it; both are in [`d2f6c14`](https://github.com/KristjanHS/claudeconf/commit/d2f6c14).

Files: [`skills/impag/`](../.claude/skills/impag/SKILL.md),
[`agents/code-reviewer.md`](../.claude/agents/code-reviewer.md),
[`references/subagent-dispatch.md`](../.claude/references/subagent-dispatch.md).

## Cost budget: stop a run before it burns its context

After each commit the budget hook reads the exact token count. At 120k, 150k and 175k it just says keep
going; at 200k, the mark where the statusline turns yellow, it tells the run to wrap up. Compaction can
still happen. When it does, the snapshot hooks save state first and point back to it afterwards.

Files: [`impag-budget-check.py`](../.claude/hooks/impag-budget-check.py),
[`statusline.sh`](../.claude/statusline.sh), [`pre-compact.py`](../.claude/hooks/pre-compact.py),
[`post-compact-restore.py`](../.claude/hooks/post-compact-restore.py).
