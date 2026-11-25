# Edit and plan gotchas

## Bash reads don't satisfy Edit's Read precondition

Edit requires a prior Read *tool* call on the exact path — `head`/`sed -n`/`grep` via Bash expose the content but don't register, so the Edit fails with "File has not been read yet". The `Grep` tool doesn't warm a file either. When previewing a file you intend to Edit, use Read (with `offset`/`limit` for big files) instead of a Bash pager; a Bash preview + failed Edit + Read is three calls where one Read sufficed.

The trap is worst when the Bash sighting happened much earlier for a *different* purpose — recon at session start, edits 15+ minutes later: the content (with line numbers!) feels "known", the anchors you build from it are even correct, but the file is still cold. And batching N parallel Edits to a cold file multiplies the one error into N — all N calls are emitted before the first rejection can land, so the transcript renders as N stubborn sequential retries when it was a single decision (4× on a plan file, 2026-07-09). Prevention: before an edit *burst* on any file you haven't Read-tool-read this session, put one Read (offset/limit fine) ahead of the batch.

## Write-error taxonomy: never re-issue a failed Edit

A rejected `Edit`/`Write` is a **state** error, never a string error: the identical call re-issued will fail identically. Re-trying verbatim is the single most expensive habit available — `old_string`+`new_string` bill as *output* tokens, and each retry also regenerates the reasoning that produced them, so four blind retries cost more than the whole file would have cost to Read. The error text names which of three recoveries applies, and **re-reading fixes only one of them**:

- `File has not been read yet. Read it first before writing to it.` — the path was never Read *in this conversation*. Fires on any file that exists, including a zero-byte one you just created with `touch`/`>`, and including one a Bash pager (`head`/`sed -n`/`grep`) showed you. **Recovery:** one `Read`, then re-issue. **Prevention:** never `touch` a file you intend to `Write` — `Write` creates it, and the `touch` converts a 1-call create into `touch` + failed Write + Read + Write.
- `String to replace not found in file.` — the anchor is stale: something rewrote that text after your Read (usually *your own* `sed -i` / `>` / formatter / `git checkout`, not a "parallel process"). **Recovery:** re-Read a narrow `offset`/`limit` window around the anchor and rebuild `old_string` from what's actually there. **Prevention:** within one file a bulk rename is `Edit(replace_all=true)`, never `sed -i` — same one-call economy, no burnt read state. Sed is for sweeps spanning several files (`python-refactors-deep-dives.md` § 8); after one, treat every sed'd file's read state as burnt and re-Read a narrow window before your next Edit on it.
- `Found N matches of the string to replace, but replace_all is false.` — the anchor is not unique. The file is *fine* and your read state is current; **re-reading is pure waste**. **Recovery:** widen `old_string` with a neighbouring line, or set `replace_all: true` if all N should change.

Two verified mechanics (repro 2026-07-09) that explain why the middle case dominates: (1) staleness is **content-based, not mtime-based** — a `touch` on an already-Read file does not invalidate the Edit; (2) when a main-agent Bash command mutates a file, the harness auto-injects the changed lines and silently refreshes the read state. So the Edit stays *legal* and you rarely see "File has been modified since read" — you get "String to replace not found", which reads like a bad guess rather than staleness. That misread is what drives the retry loop. Treat any "not found" on a file you have already Read as proof the file changed under you, not as an invitation to guess again.

## Never `git checkout --` a file that also holds uncommitted work

Proving a fix works by temporarily reverting it (`sed -i` the guard out, re-run the probe, confirm it fails) is a good habit — the teardown is the trap. `git checkout -- <path>` restores the file to **HEAD**, which discards the temporary revert *and* the uncommitted fix in one stroke, silently. Either commit the fix before the sanity-revert, or undo the revert with the inverse `Edit` (never `git checkout`). Verified 2026-07-09: a `sed -i`-then-`git checkout --` teardown left the tree clean and the fix gone; only a follow-up `grep` for the guard caught it.

## Restoring a red demo with a count-1 replace hits the wrong occurrence

A red demo's teardown must restore the *exact* line it mutated. `sed -i '0,/pat/s//new/'` and `str.replace(old, new, 1)` restore the **first** match in the file, which is often a different site — a default argument in another signature, an import, a docstring echo. The tree then looks restored, the suite is green, and two lines are silently wrong. Restore by re-typing the mutated line through a **position-anchored** `Edit` (include a neighbouring line so `old_string` is unique), never a count-limited replace — and never `git checkout --` (previous section). Bit on 2026-09-19 during a deck-form red demo.

## Edit append-boundary

When appending a new function/block immediately after an existing one, scroll to the existing block's *actual* last line before building `old_string` — don't trust memory. Edit validates that `old_string` matched, not that it covered enough. A trailing assertion/comment left outside `old_string` stays put in the file and orphans into the appended block's body as a silent no-op. If unsure, anchor `old_string` on the next `def` / separator past the block.

## Landing literal control/separator chars as `\uXXXX` escapes in source

When source must encode separator/control chars *as explicit escapes* (e.g. a regex that strips U+2028/U+2029/NEL from untrusted text), do NOT type them into Edit `old_string`/`new_string` or a bash heredoc — those separators get silently normalized to plain spaces in transit, so the Edit writes spaces (or literal separators) instead of the `\u` escape sequence. Verify with `grep -nP '[^\x00-\x7f]'` or `cat -A`. To land the escaped form, rewrite the line with a small Python script using a prefix match (`for ln in lines: if ln.startswith(...)`) and `\\uXXXX` (double-backslash) in the replacement. Same trap when matching such a line for replacement: build the matcher in Python, not as an Edit `old_string`.

## `replace_all` across a comment header AND a heredoc turns docs into live code

A shell script that documents each env var twice — once in the `#`-comment header, once inside `cat <<'HELP'` — is the trap. `Edit(replace_all=true)` with a **multi-line** `new_string` prepends the leading `#` to line 1 only; inside the comment header, every continuation line lands as **live code** (`syntax error near unexpected token )`), and the heredoc copy is fine, so the diff looks symmetric. Edit the two sites separately with distinct anchors, and run `bash -n` after any `replace_all` on a script. Cost a working driver mid-run, 2026-07-17.

## A rename sweep whose stem is an ordinary English word

Before a repo-wide rename, ask whether the old identifier is also a normal word (`rot`, `late`, `stale`, `hold`, `band`, `run`). If it is, every sweep pattern must be **position-anchored** — property access (`\.rot\b`), key position (`\brot:`), the exact `CONST_ROT` casing — never bare-word, never case-insensitive. A first pass on the private-app LATE/ROT → LAG/DEEP-LAG rename (2026-08-06) matched the English verb "rot" in prose across 8 files. Size the risk *before* editing: `grep -rn '<bare pattern>' | wc -l` against the anchored pattern's count — a large gap IS the finding, and prose hits are the tell. `replace_all` leaves you no per-hit diff to catch them in.

## Plan-reality mid-execution conflicts

If a plan's load-bearing premise turns out to be wrong when you read the code (e.g. "X isn't installed" — but it is), don't silently pick a direction. Surface the conflict, execute the unambiguous sibling tasks, then append a "Correction" section to the plan doc itself listing the discovered fact + a short menu of options for the next session. Plans are first-class docs; inline addendums beat "fix the plan and re-run".

## A graft-`OWED` naming an archive-bound doc orphans its decision

`OWED: graft this into <other doc>` can outlive its target. A 2026-07-18 close-out named a plan that shipped and archived *before* the ruling landed, leaving a live decision with no home. When authoring a graft-OWED, name a fallback home that cannot archive (a rule file, an architecture-overview section, a memory file) — or file it there directly.

## Truncated Read does not satisfy Edit's read precondition

A `Read` that hits the 25k-token cap (partial view, e.g. lines 1–170 of 201 on a file with one huge line) can leave `Edit` failing with "File has not been read yet" even though the target text is in context. Fix: `Read` the remaining window (`offset` at the truncation point) — Edit then succeeds; no full re-read needed. Seen 2026-07-02 on a memory file whose frontmatter description line alone was ~20k tokens.

## A "move fetch X to cron" roster comes from the CONSUMER's runtime ids

Derive the set from what the consumer actually resolves at runtime (`FEED_OF`, `indicator.series`), never from the plan's hand-listed ids — a 2026-09-05 rung (load-tolerance P1.1) shipped off the plan's list and missed NTFS, which the registry resolved but the plan never named.

## "X is already persisted under id Y" needs the WRITER grepped

A subagent's claim that a series is already stored comes from reading the READER; grep the writer (`recordReadings`' id) before skipping the write — the same P1.1 rung skipped five series as "cronOwned" that nothing ever wrote, and they went dark.

## Verify a symlink at the exact path git names, not its parent

`ls -l`/`readlink` on the containing dir reads as "not a link" when the link is one level deeper — in
ai-coding-journey `docs/plans` is the symlink, `docs` is not. A subagent's "this path is a symlink into
repo X" claim was true while my own check said false. Test the full path the claim names.
