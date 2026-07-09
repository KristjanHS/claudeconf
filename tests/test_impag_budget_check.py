"""Tests for the /impag budget governor hook.

Covers the plan's Verification section: the exact tail-reader, the block/silent
paths, the headline compaction regression (the case the old `bytes/4` proxy
false-fired on), empty/garbage tails, and fail-open. Run with `pytest`.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _assistant_turn(input_tokens: int = 0, cache_creation: int = 0,
                    cache_read: int = 0) -> str:
    return json.dumps({
        "type": "assistant",
        "message": {"usage": {
            "input_tokens": input_tokens,
            "cache_creation_input_tokens": cache_creation,
            "cache_read_input_tokens": cache_read,
        }},
    })


def _write_jsonl(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join(lines) + ("\n" if lines else ""))
    return path


def _run_hook(hook_path: Path, transcript: Path, command: str = "git commit -m x",
              session_id: str = "test-session") -> subprocess.CompletedProcess[str]:
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "transcript_path": str(transcript),
        "session_id": session_id,
    })
    return subprocess.run([sys.executable, str(hook_path)], input=payload,
                          capture_output=True, text=True)


def _fired(result: subprocess.CompletedProcess[str]) -> bool:
    """True iff the hook emitted the budget wrap-up reminder."""
    assert result.returncode == 0, f"non-zero exit {result.returncode}: {result.stderr}"
    out = result.stdout.strip()
    if not out:
        return False
    ctx = json.loads(out).get("hookSpecificOutput", {}).get("additionalContext", "")
    return "impag-budget" in ctx


# --- read_last_turn_context (unit) ---

def test_exact_sum_of_usage_fields(budget_hook, tmp_path):
    t = _write_jsonl(tmp_path / "t.jsonl",
                     [_assistant_turn(50_000, 60_000, 25_000)])
    assert budget_hook.read_last_turn_context(t) == 135_000


def test_reads_last_assistant_turn_not_an_earlier_one(budget_hook, tmp_path):
    t = _write_jsonl(tmp_path / "t.jsonl", [
        _assistant_turn(200_000, 0, 0),
        '{"type": "user", "message": {}}',
        _assistant_turn(10_000, 5_000, 5_000),  # last turn = 20k
    ])
    assert budget_hook.read_last_turn_context(t) == 20_000


def test_no_assistant_turn_returns_zero(budget_hook, tmp_path):
    t = _write_jsonl(tmp_path / "t.jsonl",
                     ['{"type": "user", "message": {}}', "not json", ""])
    assert budget_hook.read_last_turn_context(t) == 0


def test_missing_file_returns_zero(budget_hook, tmp_path):
    assert budget_hook.read_last_turn_context(tmp_path / "nope.jsonl") == 0


def test_empty_file_returns_zero(budget_hook, tmp_path):
    t = _write_jsonl(tmp_path / "t.jsonl", [])
    assert budget_hook.read_last_turn_context(t) == 0


# --- end-to-end (stdin payload -> hook subprocess) ---

def test_block_path_fires_at_or_above_threshold(budget_hook_path, tmp_path):
    t = _write_jsonl(tmp_path / "t.jsonl",
                     [_assistant_turn(50_000, 60_000, 25_000)])  # 135k
    assert _fired(_run_hook(budget_hook_path, t)) is True


def test_block_path_fires_exactly_at_threshold(budget_hook_path, tmp_path):
    """Boundary: 130k exactly must fire (guards against >= drifting to >)."""
    t = _write_jsonl(tmp_path / "t.jsonl",
                     [_assistant_turn(130_000, 0, 0)])  # exactly HARD_STOP_TOKENS
    assert _fired(_run_hook(budget_hook_path, t)) is True


def test_silent_just_below_threshold(budget_hook_path, tmp_path):
    """Boundary: 129,999 must stay silent."""
    t = _write_jsonl(tmp_path / "t.jsonl", [_assistant_turn(129_999, 0, 0)])
    assert _fired(_run_hook(budget_hook_path, t)) is False


def test_compaction_regression_stays_silent(budget_hook_path, tmp_path):
    """Large pre-compact prefix, but the final turn reports the reset context
    (< 130k). A file-size proxy would false-fire here; the tail-reader must not.
    """
    lines = [_assistant_turn(190_000, 5_000, 5_000) for _ in range(50)]
    lines += ["x" * 2000 for _ in range(400)]  # pad file well past the byte floor
    lines.append(_assistant_turn(60_000, 20_000, 10_000))  # post-compact = 90k
    t = _write_jsonl(tmp_path / "t.jsonl", lines)
    assert t.stat().st_size > 400_000  # exceeds FALLBACK_PROBE_BYTES
    # Both trigger paths must stay silent.
    assert _fired(_run_hook(budget_hook_path, t, command="git commit -m x")) is False
    assert _fired(_run_hook(budget_hook_path, t, command="ls -la")) is False


def test_fail_open_on_missing_transcript(budget_hook_path, tmp_path):
    result = _run_hook(budget_hook_path, tmp_path / "does-not-exist.jsonl")
    assert result.returncode == 0
    assert _fired(result) is False
