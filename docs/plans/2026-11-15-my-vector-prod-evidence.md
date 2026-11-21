# Plan: my-vector "in prod since" — derived from a sustained-use receipt

- **Created:** 2026-11-15
- **Status:** ACTIVE — Stages 1–3 DONE in my-vector (c6dd28e..20a7475, reviewed); live from the next `make ship`. Stage 4 here, after `make prod-check` seals `prod/start`.
- **Goal:** the hub's my-vector "In prod since" cell is computed from git, and means sustained, stable, real use.
- **Rulings (2026-11-15):** (1) live `ship/*` receipt per green ship, **no backfill** (tagger dates are forgeable);
  (2) prod event = first day of a 7-day window of real use + zero unplanned restarts, sealed as a `prod/start` tag.
- **Rulings (2026-11-15, qimpag round):** smoke never sends speech (SayText + cloud_intent only) → real = non-loopback peer + non-empty transcript; restarts = snapshot diff minus ship windows; poll inside wire-pod; seal manual.
- **Out of scope:** backfilled tags, ledger in a tracked file, GitHub Deployments, OpenTimestamps, proving off-home use.
- **Privacy:** ledger stays in gitignored `robot/work/`; tag bodies carry counts only — no IP, ESN, hostname, tailnet name, transcript.

## Evidence in hand (2026-11-15)

- `robot/firmware/ship.sh`: pin server sha → firmware deploy (if tree differs) → smoke → push; `:202` writes robot `/data/myvector/silent-start` (ship window).
- Smoke traffic carries `ConnectionId "wirepod-fork-smoke"` (`chipper/pkg/wirepod/sdkapp/fork_smoke.go:56`); real robot requests don't.
- No usage history survives: server journald = current boot only; robot journal volatile, `/data/log/keep` ≈ 20 h.

## Constants

| Name | Value |
|---|---|
| Ledger | `robot/work/usage.tsv` — `day  real  test  unplanned_restarts  tailnet` (one row/day, local date) |
| Real request | a speech stream from a non-loopback peer with a non-empty transcript; a loopback stream (fakebot, live-check) counts `test`; empty transcript (false wake) counts nowhere |
| Unplanned restart | snapshot diff poll-to-poll: boot_id change, or a vic-* `ActiveEnterTimestamp`/`NRestarts` change, whose time is outside every ship window (+120 s slack) |
| Ship window | `robot/work/ship-windows.tsv` — `start end` epochs appended by ship.sh: start at the `silent-start` write, end at ship exit (any outcome) |
| Tailnet up | tailscale0 UP at every successful poll that day, ≥ 1 successful poll |
| Poll | hourly loop inside wire-pod over the `robot/env.sh` ssh lane; state in `robot/work/usage-poll.state` |
| Final day | before today AND before the day of the last saved robot poll (`usage-poll.state` mtime); prod-check tags `origin/main` |
| Window | 7 consecutive days, each `real ≥ 5`, `unplanned_restarts = 0`, `tailnet = up` (defaults; Stage 3 test pins them) |
| Seal | annotated tag `prod/start` on the HEAD at sealing; body = the 7 ledger rows; created once, never moved |

## Stage 1 — live ship receipts (my-vector)

- `ship.sh`: after green smoke, before push: `git tag -a ship/<YYYYMMDD-HHMM>-<sha7>`; push `--follow-tags`.
- Body keys: `server <sha>` · `fw-tree <hash|unchanged>` · `smoke full|server PASS` · `link tailnet|lan`.
- Test: a receipt never matches `[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+`; a failed ship creates no tag.

## Stage 2 — usage ledger (my-vector)

- Server: chipper counts real vs smoke requests per day → appends/updates today's ledger row (counts only).
- Robot: hourly poll in wire-pod over the existing ssh lane → unplanned restarts (snapshot diff minus ship windows) + tailnet up.
- ship.sh appends the ship window (start at the `silent-start` write, end in its exit trap).
- Tests: a loopback stream lands in `test`, never `real`; an empty transcript counts nowhere; a restart inside a ship window is not counted; a boot_id change outside one is.

## Stage 3 — window checker + seal (my-vector)

- `make prod-check`: scans the ledger for the first qualifying 7-day window; prints it, exit 0 found / 3 not yet.
- Manual only (no auto-seal). On first find it creates + pushes `prod/start` (refuses if the tag exists); recomputation from the ledger must reproduce the body.
- Tests: a 6-day run → 3; one `real = 4` day breaks the window; a restart day breaks it; 7 good days → rows match.

## Stage 4 — generator key (claudeconf; blocked on `prod/start` existing)

- `prod_since_tag = "prod/start"` → `YYYY-MM` of the first row's `day` in the tag body; mutually exclusive with `prod_since`; absent tag → `—`.
- Definition: "first day of 7 consecutive days of real voice use with zero unplanned restarts (`prod/start` tag)".
- Tests: fixture tag body → month of row 1 (not tagger date); both keys → exit 2. Then config, `--hub README.md`, `--check` → 0, review, archive.
