#!/usr/bin/env python3
"""
agent-model-pin-gate — global PreToolUse hook on Agent.

Blocks (exit 2) an Agent call whose `model` family differs from the `model:` pin in
the named subagent's definition ($CLAUDE_PROJECT_DIR or cwd /.claude/agents/, then ~/.claude/agents/;
<name>.md first, else the file whose `name:` matches).
Families: opus/sonnet/haiku/fable, read from an alias or a full ID (claude-opus-4-8).

No in-band bypass: the cheap read-only tier is `Explore`, not a downshifted pinned agent.
Fail-open on unexpected errors. Blocks logged to ~/.claude/state/agent-model-pin-blocks.log.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

LOG_PATH = Path.home() / ".claude" / "state" / "agent-model-pin-blocks.log"
FAMILY = re.compile(r"(?<![a-z])(opus|sonnet|haiku|fable)(?![a-z])")
MODEL_LINE = re.compile(r"^model:[ \t]*[\"']?([^\"'\s#]+)", re.MULTILINE)
NAME_LINE = re.compile(r"^name:[ \t]*[\"']?([^\"'\s#]+)", re.MULTILINE)


def family(model: str) -> str | None:
    m = FAMILY.search(model.lower())
    return m.group(1) if m else None


def frontmatter(path: Path) -> str:
    lines = path.read_text(encoding="utf-8", errors="replace").lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            return "\n".join(lines[1:i])
    return ""


def definition(root: Path, agent: str) -> str | None:
    path = root / f"{agent}.md"
    if path.is_file():
        return frontmatter(path)
    if not root.is_dir():
        return None
    for path in sorted(root.glob("*.md")):
        fm = frontmatter(path)
        m = NAME_LINE.search(fm)
        if m and m.group(1) == agent:
            return fm
    return None


def pinned_model(agent: str, project_dir: str | None) -> str | None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", agent):
        return None
    roots = [Path(project_dir) / ".claude" / "agents"] if project_dir else []
    roots.append(Path.home() / ".claude" / "agents")
    for root in roots:
        fm = definition(root, agent)
        if fm is not None:
            m = MODEL_LINE.search(fm)
            return m.group(1) if m else None
    return None


def log_block(payload: dict, agent: str, pinned: str, requested: str) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "session_id": payload.get("session_id"),
            "cwd": payload.get("cwd"),
            "subagent_type": agent,
            "pinned": pinned,
            "requested": requested,
        }
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except OSError:
        pass


def main() -> int:
    payload = json.load(sys.stdin)
    if payload.get("tool_name") != "Agent":
        return 0
    tool_input = payload.get("tool_input") or {}
    requested = tool_input.get("model")
    agent = tool_input.get("subagent_type")
    if not requested or not agent or agent == "fork":
        return 0
    pinned = pinned_model(
        agent, os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd")
    )
    pin_family = family(pinned) if pinned else None
    if pin_family is None:
        return 0
    if family(requested) == pin_family:
        return 0
    log_block(payload, agent, pinned, requested)
    sys.stderr.write(
        f"agent-model-pin-gate BLOCKED: `{agent}` is pinned to model `{pinned}`; this call "
        f"asked for `{requested}`. Re-dispatch WITHOUT the `model` parameter so the pin holds. "
        "For a cheap read-only agent, dispatch `Explore` (the Haiku tier) instead of "
        "downshifting a pinned agent.\n"
    )
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
