# How the system works

The four layers from [Why this exists](../README.md#-why-this-exists), drawn as the loop they form.
What a session learns goes back into the rules.

```
  rules ──► gates ──► review loop ──► cost budget
    ▲                                      │
    └──────── /retro, /reflect ◄───────────┘
```

Each layer below names the files it lives in, what it stops, and where the evidence is. The detail
stays in the [README](../README.md). This page links to it and does not repeat it.

## Rules: say what good looks like

- **Lives in:**
  - [`.claude/CLAUDE.md`](../.claude/CLAUDE.md) keeps only the always-on rules inline and points
    at everything else.
  - [`.claude/rules/`](../.claude/rules/) holds 4 path-gated rules. Each body loads only when a file
    matching its `paths:` frontmatter is touched.
  - [`.claude/references/`](../.claude/references/) holds longer references that load when a pointer fires.
- **Stops:** rule text you don't need riding along on every turn. That is the bloat described in
  [The problem](../README.md#-the-problem).
- **Evidence:** [progressive disclosure keeps rule bodies out of every turn](../README.md#-does-this-actually-work).

## Gates: flag or block the output that isn't

- **Lives in:**
  - [`docs-bloat-gate.py`](../.claude/hooks/docs-bloat-gate.py) is a `PreToolUse` hook on Write,
    Edit and Bash. It gives advisory nudges for slop, low density and new audit files. Only the
    opt-in size ratchet blocks.
  - [`rules/testing.md`](../.claude/rules/testing.md) is the test value gate: five questions asked
    before any test is written.
  - This repo's own commit gates:
    - [`hooks/pre-commit`](../hooks/pre-commit) runs gitleaks on staged files and the identity/PII
      check.
    - [`hooks/pre-push`](../hooks/pre-push) re-checks the working tree (gitleaks) and tracked
      files (identity/PII) before push; CI gitleaks then scans every pushed commit.
    - CI runs [`tests.yml`](../.github/workflows/tests.yml) and [`gitleaks.yml`](../.github/workflows/gitleaks.yml).
    - [`test_doc_links.py`](../tests/test_doc_links.py) fails on a dead anchor or path in these pages.
- **Stops or nudges against:**
  - a bloated `.md` getting into future context;
  - a test that can't fail on a real bug;
  - a credential, private path or dead link reaching the public repo.
- **Evidence:** the tax is written up, not hidden. See
  [What it costs you](../README.md#-what-it-costs-you) and the false positives in
  [When this isn't worth it](../README.md#-when-this-isnt-worth-it).

## Review loop: catch what slips past the gates

- **Lives in:**
  - [`skills/impag/`](../.claude/skills/impag/SKILL.md) runs a plan one stage at a time. At each
    stage boundary it runs the full suite, then sends the stage's commits to a fresh `code-reviewer`
    subagent.
  - [`references/subagent-dispatch.md`](../.claude/references/subagent-dispatch.md) has the dispatch
    rules.
  - [`brutal-honesty-review`](../.claude/skills/brutal-honesty-review/),
    [`systematic-debugging`](../.claude/skills/systematic-debugging/) and
    [`testing-anti-patterns`](../.claude/skills/testing-anti-patterns/) are the critique skills.
- **Stops:** authors grading their own work. The reviewer starts in a fresh context and reads the
  diff, not the reasoning that produced it.
- **Evidence:**
  - The [code-review dispatch benchmark](../.claude/references/subagent-dispatch.md#code-review-dispatch--evidence)
    found that the bundled `/code-review` caught no more than a plain `code-reviewer` subagent, at
    many times the tokens.
  - The doc-link checker is a worked trail. Its first run
    ([`d2f6c14`](https://github.com/KristjanHS/claudeconf/commit/d2f6c14)) found a dead anchor in
    `ADOPT.md`. The fresh review then found slug and code-fence gaps the author had missed
    ([`d2f6c14`](https://github.com/KristjanHS/claudeconf/commit/d2f6c14)).

## Cost budget: stop a run before it burns its context

- **Lives in:**
  - [`impag-budget-check.py`](../.claude/hooks/impag-budget-check.py) is a `PostToolUse` hook on
    Bash. It reads the exact token count and sends a wrap-up at 200k.
  - [`statusline.sh`](../.claude/statusline.sh) shows the same number live.
  - [`pre-compact.py`](../.claude/hooks/pre-compact.py) and
    [`post-compact-restore.py`](../.claude/hooks/post-compact-restore.py) cover a compaction that
    happens anyway: they snapshot state, then re-orient from it.
- **Stops:** a long run sliding into auto-compaction. Compaction keeps a fraction of the window and
  drops the reasoning that lived only in the conversation.
- **Evidence:** the [statusline renders](../README.md#-does-this-actually-work), and
  [what happened in two real runs](../README.md#-the-budget-governor-detail) when the governor fired.

## Adopting it

Piece-by-piece steps are in [ADOPT.md](../ADOPT.md).
