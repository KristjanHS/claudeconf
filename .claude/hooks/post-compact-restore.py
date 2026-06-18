#!/usr/bin/env python3
"""SessionStart(compact|resume) hook — print recovery nudge from newest snapshot.

Why it saves context: pairs with pre-compact.py. After a compaction or resume,
it surfaces the recovery pointer the snapshot recorded (active plan, current
task, where to find the full pre-compact transcript), so Claude can re-orient
from a cheap pointer instead of re-reading or re-deriving lost state.

Fail-open: any failure exits 0 so session startup is never blocked.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def slugify_cwd(cwd: Path) -> str:
    return str(cwd).replace("/", "-")


def newest_snapshot(snapshots_dir: Path) -> Path | None:
    try:
        entries = [p for p in snapshots_dir.iterdir() if p.is_dir()]
    except OSError:
        return None
    if not entries:
        return None
    entries.sort(key=lambda p: p.name, reverse=True)
    return entries[0]


def main() -> None:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    source = payload.get("source")
    if source not in ("compact", "resume"):
        return

    cwd_slug = slugify_cwd(Path.cwd())
    snapshots_dir = Path.home() / ".claude" / "projects" / cwd_slug / "snapshots"
    snap = newest_snapshot(snapshots_dir)
    if not snap:
        return
    sidecar_path = snap / "sidecar.json"
    try:
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    nudge = sidecar.get("recovery_nudge")
    if isinstance(nudge, str) and nudge:
        print(nudge)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
