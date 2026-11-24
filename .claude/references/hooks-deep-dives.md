# Hook I/O — deep dives

Pulled from `~/.claude/rules/hooks.md` when you're writing or shipping a **PreToolUse blocking hook** (a Bash
write-gate or similar). The rule keeps the always-on I/O contract (bounded reads, fail-open, stdin
sanitization, the stdout-routing table); these three sections are the write-gate specifics.

## Bash write-gate regex must distinguish read from write

PreToolUse hooks that block Bash writes to gated paths must match write-*actions*, not bare verb-presence. A
regex like `(sed|tee|cat|>|>>)` paired with "any gated path appears in the command" produces self-blocks:
`git commit -m "$(cat <<EOF\nupdates docs/spec.md\nEOF\n)"` matches because `cat` appears AND `docs/spec.md`
appears, but it's a heredoc input + commit-message mention, not a write.

Match only true write-actions paired with the target path:
- `>` or `>>` followed by gated path (`>>?\s*['\"]?<gated-path-regex>`)
- `tee` (with optional flags) followed by gated path
- `sed -i` / `sed --in-place` operating on gated path

Read-only commands (`grep`, `git log`, `cat <path>` without redirect, `sed` without `-i`) and commit messages
mentioning the path must pass.

Apply token-level matching to EVERY check in the hook, not most of them — one leftover raw-text
`re.search(stage_text)` among token-level siblings reintroduces the self-block class (2026-07-02:
`destructive-bash-gate` shipped green with exactly this; a quoted `>> ~/.ssh/…` in a commit message blocked).
And write an allow-path regression PER check class — a "no self-block" test for `rm` doesn't cover the
redirect check.

## Write-gate coverage: expansion and pipe-to-shell classes a naive gate misses

A destructive-command gate built from a literal-token regex has predictable blind spots. When shipping one, add
an explicit test (and ideally a match rule) for each:

- **Brace-default / parameter expansions** — `rm -rf ${HOME:-/}`, `rm -rf ${VAR:=/}` reach a dangerous path
  through expansion that the literal `rm -rf /` / `rm -rf $HOME` patterns never see.
- **Pipe-to-shell equivalents beyond `bash`/`sh`** — a "reject `curl … | sh`" check that enumerates shell
  binaries often omits `source`, `.`, and `eval`, which execute fetched/interpolated text just as effectively.
- **Test-harness exec-bit assumption** — a bats suite that invokes the gate via `python3 <hook>` (rather than
  executing it directly) still passes if the hook loses its exec bit, masking a real "hook silently not running"
  regression. Assert the hook is executable, or invoke it the way the live harness will.

(Concrete instance: the 2026-07-02 `destructive-bash-gate` review flagged all three as open gaps.)

## PreToolUse blocks the whole compound bash command, not sub-commands

When PreToolUse rejects a `cmd1 && cmd2` invocation, neither half runs — bash never executes. Staged state
from `git add` does NOT materialize for a follow-up commit. Plan write-gate test cases against the actual
rollout command shape (including `cat <<EOF` heredoc messages) BEFORE shipping; debugging a self-blocked
rollout consumes the budget you saved by deferring the test.

## An advisory band phrased as a ratio reads as a stop

A budget/threshold hook whose message says `~Nk of 130k` anchors as "almost at the wall" no matter how much
reassurance follows — measured on the impag budget bands, a band explicitly saying *keep going* was obeyed as
"the wrap-up zone" at 122k. The denominator does the persuading, not the sentence. Fix pattern: **lead with the
instruction** (`Budget FYI, not a checkpoint — keep going`), demote the count to a bare trailing `(~Nk)` with
no `/cap`, and keep any keep-going clause conditional on work actually remaining, so the band never manufactures
busywork against a genuine early finish.

## Shipping a blocking hook: deliverable checklist

A new PreToolUse blocking hook is not done at "tests pass." Before declaring the stage closed:

1. **Demonstrate both block AND allow paths to the user.** Internal allow-path tests don't satisfy a reviewer
   who hasn't seen them — surface a table of useful-edit cases that pass. The block paths are obvious from the
   spec; the allow paths are where the gate's usability lives.
2. **Add a troubleshooting playbook to the natural reference.** For project hooks:
   `<project>/.claude/hooks/README.md`. For global hooks: `~/.claude/hooks/README.md`. The design doc captures
   *why*; the README captures *how do I unstick myself when it blocks me*. Cover at minimum: how to read the
   stderr message, the four bypass options, isolation-testing the hook from the CLI, inspecting the override
   log, and temporary disable.
3. **Wire the README pointer from the user-visible surface.** The L1 rule (CLAUDE.md or equivalent) that
   mentions the hook should reference the README, not the design doc. Design docs are write-time artifacts;
   READMEs are read-time.
