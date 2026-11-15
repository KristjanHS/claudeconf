"""scripts/agentic_stats.py against throwaway git repos."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REPO_ROOT

_spec = importlib.util.spec_from_file_location(
    "agentic_stats", REPO_ROOT / "scripts" / "agentic_stats.py"
)
assert _spec is not None and _spec.loader is not None
stats = importlib.util.module_from_spec(_spec)
sys.modules["agentic_stats"] = stats
_spec.loader.exec_module(stats)


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def commit(repo: Path, files: dict[str, str], msg: str = "c") -> None:
    for rel, body in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(body)
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", msg)


def make_repo(tmp_path: Path, files: dict[str, str], name: str = "r") -> Path:
    repo = tmp_path / name
    git(tmp_path, "init", "-q", str(repo))
    commit(repo, files)
    return repo


def write_config(tmp_path: Path, body: str) -> Path:
    cfg = tmp_path / "cfg.toml"
    cfg.write_text(body)
    return cfg


MIXED = {
    "src/a.test.ts": 'it("a", () => {})\n  test("b", () => {})\nconst it2 = 1\n',
    "tests/test_x.py": "def test_one():\n    pass\n\nasync def test_two():\n    pass\n",
    "pkg/x_test.go": "func TestA(t *testing.T) {}\nfunc helper() {}\n",
    "vendor/test_v.py": "def test_vendored():\n    pass\n",
    ".claude/skills/s/test_s.py": "def test_skill():\n    pass\n",
    "lib/notatest.py": "def test_lookalike():\n    pass\n",
}


def test_count_tests_per_lang(tmp_path):
    repo = make_repo(tmp_path, MIXED)
    assert stats.count_tests(repo, ["ts"], []) == 2
    assert stats.count_tests(repo, ["go"], []) == 1
    # vendor counted until excluded; .claude always excluded; lib/notatest.py never matches a test glob
    assert stats.count_tests(repo, ["py"], []) == 3
    assert stats.count_tests(repo, ["py"], ["vendor"]) == 2


def test_count_tests_head_only(tmp_path):
    repo = make_repo(tmp_path, MIXED)
    (repo / "tests" / "test_new.py").write_text("def test_uncommitted():\n    pass\n")
    with (repo / "tests" / "test_x.py").open("a") as f:
        f.write("\ndef test_unstaged_edit():\n    pass\n")
    assert stats.count_tests(repo, ["py"], ["vendor"]) == 2


def test_main_prints_tests_row(tmp_path, capsys):
    repo = make_repo(tmp_path, MIXED)
    cfg = write_config(
        tmp_path,
        f'[[repo]]\nname = "demo"\npath = "{repo.name}"\nlangs = ["py", "go"]\n',
    )
    assert stats.main(["--config", str(cfg)]) == 0
    out = capsys.readouterr().out
    assert "### demo" in out
    assert "| Tests | 4 |" in out


@pytest.mark.parametrize(
    "body, needle",
    [
        ('[[repo]]\nname = "a"\npath = "missing"\nlangs = []\n', "not a git repo"),
        ('[[repo]]\nname = "a"\npath = "r"\nlangs = ["rust"]\n', "unknown lang"),
        ('[[repo]]\nname = "a"\npath = "r"\ntypo = 1\n', "unknown key"),
        ('title = "x"\n', "no [[repo]]"),
    ],
)
def test_bad_config_exits_2(tmp_path, capsys, body, needle):
    make_repo(tmp_path, MIXED)
    cfg = write_config(tmp_path, body)
    assert stats.main(["--config", str(cfg)]) == 2
    assert needle in capsys.readouterr().err


def test_example_config_runs(capsys):
    assert (
        stats.main(
            ["--config", str(REPO_ROOT / "scripts" / "agentic-stats.example.toml")]
        )
        == 0
    )
    assert "| Tests |" in capsys.readouterr().out
