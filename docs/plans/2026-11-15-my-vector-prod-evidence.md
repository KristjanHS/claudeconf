# Plan: my-vector "in prod since" — derived from ship receipts

- **Created:** 2026-11-15
- **Status:** ACTIVE — Stage 1 runs in a **my-vector** session (cross-project); Stage 2 here.
- **Goal:** the hub's my-vector "In prod since" cell is computed from git, not a manual string.
- **Ruling (2026-11-15):** option A — annotated `ship/*` tag per green ship; prod event = earliest receipt with `link: tailnet`.
- **Out of scope:** a ledger file (B), GitHub Deployments (C), proving off-home use (smoke runs docked).

## Evidence in hand (2026-11-15)

- `robot/firmware/ship.sh`: pin server sha → firmware deploy (if tree differs) → smoke → `git push`; robot marker `/data/myvector/firmware-tree` written only after green full smoke.
- `robot/work/ship-logs/` (gitignored): 20 logs from 2026-11-10; first green 20261110-083930 `8c564e7`; first green with `ok: tailscale: logged in` 20261110-194605 `6dac3c9`.

## Stage 1 — ship receipts (my-vector session)

- `ship.sh`: after the green smoke, before its push: `git tag -a ship/<YYYYMMDD-HHMM>-<sha7>`; push with `--follow-tags`.
- Receipt body, fixed keys: `server <sha>` · `fw-tree <hash|unchanged>` · `smoke full|server PASS` · `link tailnet|lan`.
- ⛔ No IP, serial, hostname or tailnet name in the receipt (public repo); a test greps a receipt for `[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+`.
- Backfill: one tag per green log (exit 0), tagger date = log timestamp (`GIT_COMMITTER_DATE`), `link` from the log's tailscale line.
- Falsifier: `git tag -l 'ship/*' --format='%(contents)' | grep -c 'link tailnet'` ≥ 1; failed logs (exit ≠ 0) have no tag.

## Stage 2 — generator key (claudeconf)

- `prod_since_tag = { pattern = "ship/*", body = "link tailnet" }` → `YYYY-MM` of the earliest matching tag's tagger date; mutually exclusive with `prod_since`.
- Definition: "month of first `ship/*` tag with `link tailnet` (green server + robot smoke)"; no match → `—`.
- Tests: fixture tags with/without the body line → earliest qualifying month; both keys set → exit 2.
- Config: my-vector in the `--config` file; `--hub README.md`, then `--check` → 0; review; archive.
