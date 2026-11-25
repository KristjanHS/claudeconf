#!/usr/bin/env python3
"""
external-process-test-gate — PreToolUse Write/Edit on tests/**/*.py.

Blocks new/modified test code that drives external systems (docker, kubectl,
headless browsers, HTTP services) outside the manual tier. Forces such tests
into tests/manual/ so they don't run on every `pytest tests/ -q`.

Override sentinel:  <!-- external-process-test-gate-override: <reason ≥10> -->

Path scope:
  Fires on tests/**/*.py EXCLUDING:
   - tests/manual/**          (the carve-out: external-process tests live here)
   - tests/__init__.py        (package marker, never test bodies)
   - tests/conftest.py        (session-fixture file; project toolchain
                               subprocess use is established and scoped)

Detected patterns (scope: heavyweight external systems, per
~/.claude/references/testing-deep-dives.md "External-process tests go in a manual tier"):
  1. import of `docker` / `playwright` / `selenium`
  2. `requests.<get|post|put|delete|patch|head|options>(` HTTP call
  3. `subprocess.<run|Popen|check_call|check_output|call|getoutput>(` whose
     first arg starts with "docker" / "kubectl" / "playwright" / "selenium"
  4. `os.system("docker...")` / `os.system("kubectl...")` etc.

Why narrower than a `subprocess.run` blanket:
  Many projects legitimately run `subprocess.run([...])` for their own
  toolchain (recalc, build steps, codegen). A blanket subprocess.run match
  would false-positive on every such test edit. The narrowed match enforces
  the source rule's actual scope (docker / kubectl / headless browser) only.

Log: ~/.claude/logs/external-process-test-overrides.log (centralized; cwd
recorded per entry).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

OVERRIDE_RE = re.compile(
    r"<!--\s*external-process-test-gate-override:\s*(.{10,}?)\s*-->"
)

EXEMPT_FILES = {"tests/__init__.py", "tests/conftest.py"}
EXEMPT_PREFIX = "tests/manual/"

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "docker/playwright/selenium import",
        re.compile(
            r"^\s*(?:from|import)\s+(?:docker|playwright|selenium)\b",
            re.MULTILINE,
        ),
    ),
    (
        "requests HTTP call",
        re.compile(
            r"\brequests\.(?:get|post|put|delete|patch|head|options)\s*\("
        ),
    ),
    (
        "subprocess to external CLI",
        re.compile(
            r"\bsubprocess\.(?:run|Popen|check_call|check_output|call|getoutput)"
            r"\s*\(\s*\[?\s*['\"]?(?:docker|kubectl|playwright|selenium)\b"
        ),
    ),
    (
        "os.system to external CLI",
        re.compile(
            r"\bos\.system\s*\(\s*['\"](?:docker|kubectl|playwright|selenium)\b"
        ),
    ),
]

LOG_PATH = Path.home() / ".claude" / "logs" / "external-process-test-overrides.log"


def project_dir() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))


def relpath_or_none(file_path: str) -> str | None:
    try:
        return str(Path(file_path).resolve().relative_to(project_dir().resolve()))
    except (ValueError, OSError):
        return None


def is_gated_path(rel: str) -> bool:
    if not rel.startswith("tests/") or not rel.endswith(".py"):
        return False
    if rel in EXEMPT_FILES:
        return False
    if rel.startswith(EXEMPT_PREFIX):
        return False
    return True


def find_matches(text: str) -> list[str]:
    hits: list[str] = []
    for label, pat in PATTERNS:
        if pat.search(text):
            hits.append(label)
    return hits


def _safe_sid(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", s)[:64] or "default"


def session_id() -> str:
    sid = os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        return _safe_sid(sid)
    transcript = os.environ.get("CLAUDE_TRANSCRIPT_PATH")
    if transcript:
        return hashlib.md5(transcript.encode(), usedforsecurity=False).hexdigest()[:12]
    seed = f"{project_dir()}|{datetime.now(timezone.utc).strftime('%Y%m%d%H')}"
    return hashlib.md5(seed.encode(), usedforsecurity=False).hexdigest()[:12]


def _write_schema_header(log: Path, fields: str) -> None:
    if log.exists() and log.stat().st_size > 0:
        return
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(f"# JSONL fields: {fields} (since 2026-05-08)\n")
    except OSError:
        pass


def append_log(rel: str, hits: list[str], reason: str, tool: str) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _write_schema_header(
            LOG_PATH,
            "ts, tool, session_id, cwd, reason, file, hits, regression_test",
        )
        entry = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tool": tool,
            "session_id": session_id(),
            "cwd": str(project_dir().resolve()),
            "reason": reason,
            "file": rel,
            "hits": hits,
            "regression_test": os.environ.get("HOOK_REGRESSION_TEST") == "1",
        }
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except OSError:
        pass


def handle(payload: dict, tool: str) -> int:
    ti = payload.get("tool_input", {}) or {}
    file_path = ti.get("file_path", "")
    if not file_path:
        return 0
    rel = relpath_or_none(file_path)
    if rel is None or not is_gated_path(rel):
        return 0

    if tool == "Edit":
        added = ti.get("new_string", "") or ""
    else:  # Write
        added = ti.get("content", "") or ""
    if not added:
        return 0

    hits = find_matches(added)
    if not hits:
        return 0

    m = OVERRIDE_RE.search(added)
    if m:
        append_log(rel, hits, m.group(1).strip(), tool)
        return 0

    sys.stderr.write(
        f"external-process-test-gate: {rel} adds external-process patterns "
        f"({', '.join(hits)}) outside the manual tier.\n"
        "Per ~/.claude/references/testing-deep-dives.md: external-process tests (docker, "
        "kubectl, headless browser, live HTTP) belong in tests/manual/ — "
        "they run on demand, not in `pytest tests/ -q`.\n"
        "Unblock: move the test under tests/manual/, or add "
        "<!-- external-process-test-gate-override: <reason ≥10 chars> --> "
        "in the new content.\n"
    )
    return 2


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0
    tool = payload.get("tool_name", "")
    if tool not in ("Write", "Edit"):
        return 0
    # Per-project opt-out: an empty marker file.
    if (project_dir() / ".claude" / "external-process-test-gate.off").exists():
        return 0
    return handle(payload, tool)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
