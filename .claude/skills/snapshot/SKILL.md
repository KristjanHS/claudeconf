---
name: snapshot
description: ONLY on /snapshot. Manually snapshot this session — transcript copy + plan/todo sidecar — into the project's snapshots dir (own keep-10 pool, never evicted by automatic PreCompact snapshots).
---

# /snapshot — manual session snapshot

1. Invent a random literal token, e.g. `snap-x7k42q`. Type it literally — NEVER
   shell substitution (`$(...)`, `$RANDOM`, `$$`): the transcript records the
   *unexpanded* command text, so a substituted nonce never matches itself.
2. Run (Bash):

   ```bash
   python3 ~/.claude/hooks/pre-compact.py --manual --nonce <token>
   ```

   By execution time the token is already in this session's transcript, so the
   script identifies OUR transcript even with concurrent sessions in this
   project (nonce match beats mtime).
3. Relay the script's stdout line (snapshot path + source transcript) to the
   user — nothing more. On non-zero exit, show its stderr verbatim; the likely
   cause is cwd differing from the project the session was launched in.

Manual snapshots get a `-manual` dir suffix and their own keep-10 retention
pool in `cleanup_old` — automatic PreCompact snapshots can't evict them, and
vice versa.
