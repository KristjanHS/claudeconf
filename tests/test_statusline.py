"""Pins the trust claims in .claude/statusline.sh's header (port of dotfiles tests/statusline.bats)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import REPO_ROOT

SCRIPT = REPO_ROOT / ".claude" / "statusline.sh"
E = "\x1b"

pytestmark = pytest.mark.skipif(
    not (shutil.which("jq") and shutil.which("git")), reason="needs jq + git"
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "proj"
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(r)], check=True, env=_env(tmp_path)
    )
    return r


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    # Host git config / a hook's GIT_DIR must not reach the fixture repo; a parent work tree must not leak a label.
    base = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return {
        **base,
        "HOME": str(tmp_path),
        "GIT_CEILING_DIRECTORIES": str(tmp_path),
        **extra,
    }


def _json(tokens: int, cwd: Path | str, model: str = "Opus 5.5 (1M context)") -> str:
    usage = {
        "input_tokens": min(tokens, 1000),
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": max(tokens - 1000, 0),
    }
    return json.dumps(
        {
            "model": {"display_name": model},
            "context_window": {"current_usage": usage},
            "cost": {"total_cost_usd": 1.234},
            "rate_limits": {
                "five_hour": {"used_percentage": 12.6},
                "seven_day": {"used_percentage": 40},
            },
            "workspace": {"current_dir": str(cwd)},
        }
    )


def _run(stdin: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT)], input=stdin, capture_output=True, text=True, env=env
    )


def _plain(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", s)


def test_valid_input_renders_model_bar_tokens_dir_branch_limits_no_cost(tmp_path, repo):
    out = _run(_json(151000, repo), _env(tmp_path))
    assert out.returncode == 0
    assert out.stdout == (
        f"[Opus 5.5 (1M context)] {E}[32m█████░░░░░{E}[0m 50% {E}[2m(151k) proj[main]{E}[0m"
        f"{E}[2m | 5h:12% | 7d:40%{E}[0m\n"
    )


@pytest.mark.parametrize(
    ("tokens", "colour", "warn"),
    [
        (194999, 32, False),
        (195000, 32, True),
        (199999, 32, True),
        (200000, 33, True),
        (239999, 33, True),
        (240000, 31, True),
    ],
)
def test_budget_knobs_fire_at_200k_amber_240k_red_195k_clear_soon(
    tmp_path, repo, tokens, colour, warn
):
    out = _run(_json(tokens, repo), _env(tmp_path)).stdout
    assert f"{E}[{colour}m█" in out
    assert ("/clear soon" in out) is warn


def test_bar_stays_10_cells_past_100_percent(tmp_path, repo):
    assert (
        f"{E}[31m██████████{E}[0m 110%"
        in _run(_json(330000, repo), _env(tmp_path)).stdout
    )


def test_control_chars_in_model_and_dir_are_stripped(tmp_path):
    d = tmp_path / f"raw{E}]0;PWN\ax"
    d.mkdir()
    out = _run(_json(1000, d, f"Op{E}]52;c;SGVsbG8=\aus"), _env(tmp_path))
    assert out.returncode == 0
    plain = _plain(out.stdout)
    assert E not in plain and "\a" not in plain
    assert "[Op]52;c;SGVsbG8=us]" in plain and "raw]0;PWNx" in plain


def test_backslash_sequences_print_literally(tmp_path):
    d = tmp_path / r"a\033[5mB"
    d.mkdir()
    out = _run(_json(1000, d), _env(tmp_path)).stdout
    assert r"a\033[5mB" in out and f"{E}[5m" not in out


def test_hostile_repo_fsmonitor_does_not_execute(tmp_path, repo):
    trap = tmp_path / "PWNED"
    subprocess.run(
        ["git", "-C", str(repo), "config", "core.fsmonitor", f"touch {trap}; false"],
        check=True,
        env=_env(tmp_path),
    )
    _run(_json(1000, repo), _env(tmp_path))
    assert not trap.exists()
    # Control: plain `git status` fires the hook, so the trap is live.
    subprocess.run(
        ["git", "-C", str(repo), "status"], capture_output=True, env=_env(tmp_path)
    )
    assert trap.exists()


@pytest.mark.parametrize("stdin", ["garbage", "{}", ""])
def test_garbage_or_empty_stdin_prints_one_line_no_stderr(tmp_path, stdin):
    out = _run(stdin, _env(tmp_path))
    assert out.returncode == 0
    assert out.stdout.count("\n") == 1 and out.stderr == ""


def test_caller_env_pad_does_not_leak(tmp_path, repo):
    assert "XXXX" not in _run(_json(151000, repo), _env(tmp_path, PAD="XXXX")).stdout


def test_no_file_writes_under_home_or_repo(tmp_path, repo):
    home = tmp_path / "home"
    home.mkdir()

    def snap() -> list[tuple[str, int, int]]:
        return sorted(
            (str(p), p.stat().st_mtime_ns, p.stat().st_size)
            for root in (home, repo)
            for p in root.rglob("*")
        )

    before = snap()
    _run(_json(1000, repo), _env(tmp_path, HOME=str(home)))
    assert snap() == before


def test_no_network_command_or_eval_in_source():
    src = SCRIPT.read_text()
    assert not re.search(
        r"\b(curl|wget|nc|ncat|ssh|scp|eval|source)\b|/dev/(tcp|udp)", src
    )


def test_json_strings_never_reach_bash_arithmetic(tmp_path, repo):
    marker = tmp_path / "EXEC"
    x = f"a[$(touch {marker})]"
    payload = json.dumps(
        {
            "model": {"display_name": "x\u001f" + x},
            "context_window": {"current_usage": {"input_tokens": x}},
            "rate_limits": {"five_hour": {"used_percentage": x}},
            "workspace": {"current_dir": str(repo)},
        }
    )
    out = _run(payload, _env(tmp_path))
    assert not marker.exists()
    assert out.stderr == ""


def test_only_external_git_call_is_branch_show_current(tmp_path, repo):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "git.log"
    shim = bindir / "git"
    shim.write_text(
        f'#!/bin/bash\nprintf "%s\\n" "$*" >>"{log}"\nexec "{shutil.which("git")}" "$@"\n'
    )
    shim.chmod(0o755)
    _run(_json(1000, repo), _env(tmp_path, PATH=f"{bindir}:{os.environ['PATH']}"))
    assert sorted(set(log.read_text().splitlines())) == [
        f"-C {repo} branch --show-current"
    ]
