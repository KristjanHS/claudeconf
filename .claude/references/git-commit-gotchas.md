# Git Commit Gotchas

## `-m` must come before `--` in a pathspec'd commit

Use `git commit -- <paths>` to limit a commit to specific paths when the index is mixed — a no-pathspec `git commit` commits the WHOLE staged index, so a previously-staged `git mv`/rename gets swept into an unrelated commit.

Everything after `--` is treated as a pathspec, so argument order matters:

- **WRONG:** `git commit -- <paths> -m "msg"` → git tries to match `-m` and the message text as filenames and aborts (`pathspec '-m' did not match any file(s)`).
- **RIGHT:** `git commit -m "msg" -- <paths>` → message first, then the `--` pathspec terminator.

Alternative when you don't want to enumerate paths: unstage the unrelated changes first, then a plain `git commit` is safe.

## Multi-paragraph messages go via `-F`, never `-m "…"`

`-m` takes a **double-quoted** string, so the shell expands `` `backticks` `` (command substitution) and `$vars` before git ever sees them. A message citing a symbol as `` `limit` `` silently loses the word and emits `limit: command not found` (2026-07-17, private-app Stage 1.3 — amended via `-F`). Nothing warns you; the commit succeeds with a mangled message.

For any message longer than one plain line, or containing backticks/`$`/`!`, pipe a heredoc with a **quoted** delimiter:

```
git commit -F - <<'MSGEOF'
feat(store): collapse the alert reads to one row per fired-date

The `.limit(1)` read cannot observe a second row by construction.
MSGEOF
```

The quoted `'MSGEOF'` is what disables expansion — an unquoted `MSGEOF` re-opens the same hole. A message file plus `-F <file>` works equally well. Single-quoting `-m 'msg'` also blocks expansion but can't carry apostrophes or multiple paragraphs.

## Backticked identifiers in a `-m` message VANISH — and the commit still succeeds

The same expansion hole, in the shape you hit most often. `git commit -m "…\`cross-asset\`…"` runs command substitution on the message: backticked identifiers — the natural way to write `` `cross-asset` `` or `` `R4_HY_TAIL` `` — are silently dropped, `bash: cross-asset: command not found` scrolls past, and the commit **SUCCEEDS** with a mangled body (2026-07-31: two family names vanished from a private-app commit).

**Worse variant — the commit HANGS.** When the backticked word is a real command that reads stdin (`` `fold` ``, `` `cat` ``, `` `sort` ``), the substitution runs it against the terminal, so `git commit` never receives its `-m` argument, blocks forever and holds `.git/index.lock` — indistinguishable from a hung tool call (2026-09-20, private-app). Same fix; the quoted-delimiter heredoc is the only one safe by construction.

Fix: pass the message via a heredoc with a **quoted** delimiter (`git commit -F - <<'MSG' … MSG`, so nothing expands), or single-quote the whole `-m` argument. Never double-quote a commit message that contains backticks.

## Prove HEAD is your own commit before `--amend`

`git commit --amend` amends **whatever HEAD currently is**, not the commit you last created. When a second session commits to the same branch, HEAD can advance between your commit and your amend — the amend then silently folds your working-tree changes into *their* commit, under *their* message, and rewrites their SHA. A pathspec does **not** protect you: it scopes which files are taken from the working tree, not which commit is amended. (Same hazard as "pin background reviewers to an immutable SHA, never HEAD", on the write side.)

**Before any `--amend`:** `git log --oneline -1` and confirm the subject is the commit you just wrote. If it isn't yours, don't amend — commit the follow-up separately.

**If you already amended by mistake:** report it — never self-repair (global CLAUDE.md §Default git workflow). The fix to OFFER: `git reflog` for their original SHA, then `git reset --mixed <their-sha>` restores their commit and returns your edit unstaged; run it only when the user asks.

## `git commit -a` and a pathspec are MUTUALLY EXCLUSIVE

`git commit -a -m "msg" -- <paths>` dies with `fatal: paths '<paths> ...' with -a does not make sense`. `-a` means *every* modified tracked file, so it cannot be narrowed. In a shared or mixed-index tree the pathspec is the point — drop `-a`, and `git add <paths>` first for untracked files (2026-09-12).

## Pathspec commits skip UNTRACKED files — `git add` them first

**`git commit -a` skips untracked files too** — `-a` stages *modified tracked* files only, so a brand-new file (e.g. a test registered in a shared `vitest.shared.ts` manifest) silently stays out while the commit message claims it. The commit is then RED IN ISOLATION: its own manifest references a file that isn't in the tree at that SHA. `git add <newfile>` first, or `git status --short` after the commit and look for `??` lines the message claimed (2026-08-20, private-app `d99393a7` → backfilled by `cf6096bb`).

`git commit -m "msg" -- <path>` fails with `pathspec '<path>' did not match any file(s) known to git` when `<path>` is a new/untracked file — the pathspec only scopes content git already knows. For a new file: `git add <path> && git commit -m "msg" -- <path>` (the pathspec still protects against sweeping in other staged changes).

## `git add <files>` + a pathspec-less `git commit` ships ONLY the staged files

The inverse of the sweep-everything trap, and it fails in the direction you don't check. A pathspec-less
`git commit` (no `-a`) commits **exactly the index** — so after a narrow `git add a.ts b.ts`, a subagent's
other modified files stay in the working tree while the commit message claims them. Nothing errors: the
tree is right, the suite stays green, only `HEAD` is wrong — and the gap surfaces later as a "shipped"
stage whose code isn't in the commit (2026-07-18, private-app `3c02d80` → `cfc6d24` had to backfill the
other half).

**Always end a commit with `git status --short`.** Leftover modified files that the message claimed are
the tell. This is why the files-touched list from a subagent report is the scope contract — `git add` what
that list names, then verify nothing survived the commit.

## Directory pathspecs sweep EVERY dirty file under them

`git commit -- docs/plans/` commits ALL working-tree changes under that dir — including a foreign/user
edit you meant to exclude (2026-07-16: a user's dirty design doc rode into an unrelated archive commit).
When the tree carries edits that aren't yours, pathspec the exact FILES, never a directory. If it already rode in:
report it — never self-repair; the fix to OFFER is `git reset --soft HEAD~1`, then two commits with file-level pathspecs; run it only when the user asks.

## Pathspec BOTH paths of a `git mv`, or the rename SPLITS

Pathspec'ing only a `git mv`'s NEW path stages the addition but leaves the OLD path's deletion unstaged, so
HEAD ends up with the file at BOTH paths — a duplicate, and the rename is lost. Pathspec **both** the old
and the new path (`git commit -m "msg" -- old/x.md new/x.md`), or pathspec neither and let the plain commit
take the whole rename.

## Observe scope BEFORE staging — never chain `git status` and `git add` in one command

`git status --short && git add -A` reads as one recon-then-stage step, but the output arrives *after* the
staging decision is already made — there is no turn in which you can act on what you saw. In 2026-07-19
that swept a sibling session's `package.json` bump and an untracked plan file into `9fef72f` (backed out).
Compound commands defeat the check by construction, however correct each half is alone.

**Run `git status --short` as its own call, read it, then stage the named paths** (`git add <files>` from
the subagent's files-touched list) and commit with a file-level pathspec. `git add -A` is only safe on a
tree you have just inspected in a separate call — and on a shared branch with parallel sessions, rarely
then.

## A heredoc in a compound command binds to the LAST command, not the one you wrote it after

`git commit -F - <<'MSGEOF' … MSGEOF && git log --oneline -3` does **not** feed the heredoc to `git commit`. The shell attaches the here-document to the *whole* compound list's final redirection slot, so `git commit` gets the terminal's stdin instead — it blocks forever waiting for a message, holding `.git/index.lock`, and looks exactly like a hung tool call (2026-09-06, private-app). Killing it leaves the stale lock behind.

Never chain anything after a heredoc-fed `git commit`. Write the message to a file and use `-F <file>`, or make the commit its own command and run `git log` in a separate call.
