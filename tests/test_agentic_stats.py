"""scripts/agentic_stats.py against throwaway git repos."""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
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


def test_main_prints_tests_row(tmp_path, fake_scc, capsys):
    repo = make_repo(tmp_path, MIXED)
    cfg = write_config(
        tmp_path,
        f'[[repo]]\nname = "demo"\npath = "{repo.name}"\nlangs = ["py", "go"]\n'
        'exclude = ["vendor"]\n',
    )
    assert stats.main(["--config", str(cfg)]) == 0
    out = capsys.readouterr().out
    assert "### demo" in out
    assert "| Tests | 3 |" in out
    assert "excl. `.claude`, `vendor`; `.each`/parametrized cases count once |" in out
    assert "excl. docs/data formats, `.claude`, `vendor` |" in out


@pytest.mark.parametrize(
    "body, needle",
    [
        ('[[repo]]\nname = "a"\npath = "missing"\nlangs = []\n', "not a git repo"),
        ('[[repo]]\nname = "a"\npath = "r"\nlangs = ["rust"]\n', "unknown lang"),
        ('[[repo]]\nname = "a"\npath = "r"\ntypo = 1\n', "unknown key"),
        ('title = "x"\n', "no [[repo]]"),
        (
            '[[repo]]\nname = "a"\npath = "r"\nrelease_pattern = "v*"\n',
            "a: release_pattern",
        ),
        ('[[repo]]\nname = "a"\npath = "r"\nhub = "false"\n', "a: hub must be"),
        ('[[repo]]\nname = "a"\npath = "r"\nadr_glob = ["d/*"]\n', "a: adr_glob must"),
    ],
)
def test_bad_config_exits_2(tmp_path, capsys, body, needle):
    make_repo(tmp_path, MIXED)
    cfg = write_config(tmp_path, body)
    assert stats.main(["--config", str(cfg)]) == 2
    assert needle in capsys.readouterr().err


def test_example_config_runs(fake_scc, capsys):
    assert (
        stats.main(
            ["--config", str(REPO_ROOT / "scripts" / "agentic-stats.example.toml")]
        )
        == 0
    )
    assert "| Tests |" in capsys.readouterr().out


WORKFLOWS = {
    ".github/workflows/push.yml": "on:\n  push:\n    branches: [main]\njobs: {}\n",
    ".github/workflows/pr.yml": "on:\n  pull_request:\njobs: {}\n",
    ".github/workflows/cron.yml": "on:\n  schedule:\n    - cron: '0 0 * * *'\njobs: {}\n",
    ".github/workflows/manual.yml": "on: workflow_dispatch\njobs: {}\n",
    ".github/workflows/list.yml": "on: [push]\njobs: {}\n",
    ".github/workflows/str.yaml": "on: push\njobs: {}\n",
    ".github/workflows/quoted.yml": '"on":\n  merge_group:\njobs: {}\n',
    ".github/workflows/README.md": "on: push\n",
}


def test_count_ci_gates(tmp_path):
    repo = make_repo(tmp_path, WORKFLOWS)
    # push, pr, list, str, quoted = 5; cron + manual excluded; non-yaml ignored
    assert stats.count_ci_gates(repo) == 5


def test_count_ci_gates_none(tmp_path):
    repo = make_repo(tmp_path, {"a.txt": "x\n"})
    assert stats.count_ci_gates(repo) == 0


def test_malformed_workflow_exits_2(tmp_path, capsys):
    repo = make_repo(tmp_path, {".github/workflows/bad.yml": "on: [push\n"})
    cfg = write_config(tmp_path, f'[[repo]]\nname = "a"\npath = "{repo.name}"\n')
    assert stats.main(["--config", str(cfg)]) == 2
    assert "bad.yml" in capsys.readouterr().err


def test_count_releases(tmp_path):
    repo = make_repo(tmp_path, {"a.txt": "x\n"})
    for tag in ["v1.0", "v1.1", "v2.0-rc1", "chipper/v1", "last-cursor"]:
        git(repo, "tag", tag)
    assert stats.count_releases(repo, ["v*"], []) == 3
    assert stats.count_releases(repo, ["v*"], ["*-rc*"]) == 2
    assert stats.count_releases(repo, ["v*", "chipper/*"], ["chipper/*"]) == 3


def test_releases_unset_is_absent(tmp_path, fake_scc, capsys):
    repo = make_repo(tmp_path, {"a.txt": "x\n"})
    git(repo, "tag", "v1.0")
    cfg = write_config(tmp_path, f'[[repo]]\nname = "a"\npath = "{repo.name}"\n')
    assert stats.main(["--config", str(cfg)]) == 0
    assert "| Releases | — | not tracked |" in capsys.readouterr().out


FAKE_SCC = """#!{python}
import json, os, sys
names = {{".py": "Python", ".md": "Markdown", ".json": "JSON"}}
code = {{}}
for root, _, files in os.walk(sys.argv[-1]):
    for f in files:
        lang = names.get(os.path.splitext(f)[1], "Other")
        with open(os.path.join(root, f), "rb") as fh:
            code[lang] = code.get(lang, 0) + sum(1 for _ in fh)
print(json.dumps([{{"Name": k, "Code": v}} for k, v in code.items()]))
"""


@pytest.fixture
def fake_scc(tmp_path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    scc = bindir / "scc"
    scc.write_text(FAKE_SCC.format(python=sys.executable))
    scc.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")


@pytest.fixture
def no_scc(tmp_path, monkeypatch):
    bindir = tmp_path / "nobin"
    bindir.mkdir()
    git_bin = shutil.which("git")
    assert git_bin is not None
    (bindir / "git").symlink_to(git_bin)
    monkeypatch.setenv("PATH", str(bindir))


LOC_FILES = {
    "src/a.py": "a = 1\nb = 2\nc = 3\n",
    "README.md": "# t\n\nbody\n",
    "data.json": "{}\n",
    "vendor/v.py": "v = 1\n",
    ".claude/hooks/h.py": "h = 1\n",
}


def test_count_loc_skips_docs_and_excludes(tmp_path, fake_scc):
    repo = make_repo(tmp_path, LOC_FILES)
    # src/a.py (3) + vendor/v.py (1); Markdown/JSON skipped; .claude always excluded
    assert stats.count_loc(repo, []) == 4
    assert stats.count_loc(repo, ["vendor"]) == 3


def test_count_loc_skips_absolute_symlink(tmp_path, fake_scc):
    repo = make_repo(tmp_path, LOC_FILES)
    (repo / "abs-link").symlink_to("/etc/hostname")
    commit(repo, {})
    assert stats.count_loc(repo, []) == 4


def test_count_loc_head_only(tmp_path, fake_scc):
    repo = make_repo(tmp_path, LOC_FILES)
    (repo / "src" / "untracked.py").write_text("x = 1\ny = 2\n")
    (repo / "src" / "a.py").write_text("a = 1\n")
    assert stats.count_loc(repo, ["vendor"]) == 3


def test_missing_scc_exits_2_never_zero(tmp_path, no_scc, capsys):
    repo = make_repo(tmp_path, LOC_FILES)
    cfg = write_config(tmp_path, f'[[repo]]\nname = "a"\npath = "{repo.name}"\n')
    assert stats.main(["--config", str(cfg)]) == 2
    captured = capsys.readouterr()
    assert "scc not on PATH" in captured.err
    assert "| Lines |" not in captured.out


def test_adrs_and_prod_since_rows(tmp_path, fake_scc, capsys):
    repo = make_repo(
        tmp_path,
        {"docs/adr/0001-x.md": "x\n", "docs/adr/0002-y.md": "y\n", "docs/n.md": "n\n"},
    )
    cfg = write_config(
        tmp_path,
        f'[[repo]]\nname = "a"\npath = "{repo.name}"\n'
        'adr_glob = "docs/adr/*.md"\nprod_since = "2026-06"\n'
        f'[[repo]]\nname = "b"\npath = "{repo.name}"\n',
    )
    assert stats.main(["--config", str(cfg)]) == 0
    out = capsys.readouterr().out
    block_a, block_b = out.split("### b")
    assert "| ADRs | 2 |" in block_a and "| In prod since | 2026-06 |" in block_a
    assert "| ADRs | — |" in block_b and "| In prod since | — |" in block_b


@pytest.mark.parametrize("value", ['"2026-6"', '"June 2026"', "202606"])
def test_bad_prod_since_exits_2(tmp_path, capsys, value):
    repo = make_repo(tmp_path, {"a.txt": "x\n"})
    cfg = write_config(
        tmp_path, f'[[repo]]\nname = "a"\npath = "{repo.name}"\nprod_since = {value}\n'
    )
    assert stats.main(["--config", str(cfg)]) == 2
    assert "prod_since" in capsys.readouterr().err


def _upstream_repo(tmp_path: Path) -> Path:
    repo = make_repo(
        tmp_path, {"tests/test_up.py": "def test_u():\n    pass\n", "up.py": "u = 1\n"}
    )
    git(repo, "branch", "upstream-main")
    commit(
        repo,
        {
            "tests/test_mine.py": "def test_a():\n    pass\n\ndef test_b():\n    pass\n",
            "mine.py": "m = 1\nn = 2\n",
        },
    )
    return repo


def test_upstream_delta(tmp_path, fake_scc, capsys):
    repo = _upstream_repo(tmp_path)
    cfg = write_config(
        tmp_path,
        f'[[repo]]\nname = "a"\npath = "{repo.name}"\nlangs = ["py"]\n'
        'upstream_ref = "upstream-main"\nupstream_name = "wire-pod"\n',
    )
    assert stats.main(["--config", str(cfg)]) == 0
    out = capsys.readouterr().out
    # HEAD 3 tests vs 1 upstream; HEAD 2+1+5+2 = 10 py lines vs 2+1 = 3 upstream
    assert "| Tests | +2 over wire-pod |" in out
    assert "| Lines | +7 over wire-pod |" in out
    assert "(delta vs wire-pod) |" in out


def test_upstream_delta_negative_not_clamped(tmp_path, fake_scc, capsys):
    repo = _upstream_repo(tmp_path)
    git(repo, "rm", "-q", "tests/test_mine.py", "tests/test_up.py")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "drop")
    cfg = write_config(
        tmp_path,
        f'[[repo]]\nname = "a"\npath = "{repo.name}"\nlangs = ["py"]\n'
        'upstream_ref = "upstream-main"\n',
    )
    assert stats.main(["--config", str(cfg)]) == 0
    assert "| Tests | -1 over upstream-main |" in capsys.readouterr().out


def test_unresolvable_upstream_exits_2(tmp_path, fake_scc, capsys):
    repo = make_repo(tmp_path, {"a.txt": "x\n"})
    cfg = write_config(
        tmp_path,
        f'[[repo]]\nname = "a"\npath = "{repo.name}"\nupstream_ref = "nope/main"\n',
    )
    assert stats.main(["--config", str(cfg)]) == 2
    assert "does not resolve" in capsys.readouterr().err


START, END = stats.BLOCK_MARKERS


def test_replace_between_idempotent_and_preserves_outside():
    text = f"head\n{START}\nold\n{END}\ntail  \n"
    once = stats.replace_between(text, START, END, "new\n")
    assert once == f"head\n{START}\nnew\n{END}\ntail  \n"
    assert stats.replace_between(once, START, END, "new\n") == once


@pytest.mark.parametrize(
    "text",
    [
        f"{START}\nx\n",  # end missing
        f"{START}\n{START}\n{END}\n",  # duplicate start
        f"{END}\nx\n{START}\n",  # reversed
    ],
)
def test_replace_between_bad_markers(text):
    with pytest.raises(stats.InputError):
        stats.replace_between(text, START, END, "b\n")


def _check_setup(tmp_path: Path) -> tuple[Path, Path, str]:
    repo = make_repo(tmp_path, {"tests/test_a.py": "def test_a():\n    pass\n"})
    cfg = write_config(
        tmp_path, f'[[repo]]\nname = "a"\npath = "{repo.name}"\nlangs = ["py"]\n'
    )
    block = stats.render_block(stats.collect(stats.load_config(cfg)[0]))
    return repo, cfg, block


def test_check_fresh_stale_and_skip(tmp_path, fake_scc, capsys):
    repo, cfg, block = _check_setup(tmp_path)
    assert stats.main(["--config", str(cfg), "--check"]) == 0
    assert "skip: a has no agentic-stats markers" in capsys.readouterr().err
    readme = repo / "README.md"
    readme.write_text(f"# a\n{START}\n{block}{END}\n")
    assert stats.main(["--config", str(cfg), "--check"]) == 0
    readme.write_text(readme.read_text().replace("| Tests | 1 |", "| Tests | 9 |"))
    assert stats.main(["--config", str(cfg), "--check"]) == 1
    assert "stale:" in capsys.readouterr().err


@pytest.mark.parametrize("tail", [f"{END}\n{END}\n", "no end marker\n"])
def test_check_bad_markers_exits_2(tmp_path, fake_scc, capsys, tail):
    repo, cfg, block = _check_setup(tmp_path)
    (repo / "README.md").write_text(f"{START}\n{block}{tail}")
    assert stats.main(["--config", str(cfg), "--check"]) == 2
    assert "README.md" in capsys.readouterr().err


def test_block_escapes_pipes_in_cells():
    rows = [stats.Row("Tests", "1", stats.tests_definition(["ts"], []))]
    table = stats.render_block(rows).splitlines()
    assert all(len(re.findall(r"(?<!\\)\|", line)) == 4 for line in table)


HUB_START, HUB_END = stats.HUB_MARKERS


def _hub_setup(tmp_path: Path) -> tuple[Path, Path]:
    pub = make_repo(tmp_path, {"tests/test_a.py": "def test_a():\n    pass\n"}, "pub")
    priv = make_repo(tmp_path, {"a.txt": "x\n"}, "priv")
    cfg = write_config(
        tmp_path,
        f'[[repo]]\nname = "pub"\npath = "{pub.name}"\nlangs = ["py"]\nhub = true\n'
        'url = "https://example.invalid/pub"\nprod_since = "2026-06"\n'
        f'[[repo]]\nname = "priv"\npath = "{priv.name}"\n'
        f'[[repo]]\nname = "gopub"\npath = "{pub.name}"\nlangs = ["go"]\nhub = true\n',
    )
    hub = tmp_path / "HUB.md"
    hub.write_bytes(f"# hub\r\n{HUB_START}\r\n{HUB_END}\r\nafter\r\n".encode())
    return cfg, hub


def test_hub_write_then_check(tmp_path, fake_scc):
    cfg, hub = _hub_setup(tmp_path)
    assert stats.main(["--config", str(cfg), "--hub", str(hub), "--repo", "pub"]) == 2
    assert stats.main(["--config", str(cfg), "--hub", str(hub)]) == 0
    raw = hub.read_bytes()
    assert raw.startswith(f"# hub\r\n{HUB_START}".encode())
    assert raw.endswith(f"{HUB_END}\r\nafter\r\n".encode())
    text = raw.decode()
    assert (
        "| Repo | Tests | CI gates | ADRs | Releases | Lines | In prod since |" in text
    )
    assert (
        "| [pub](https://example.invalid/pub) | 1 | 0 | — | — | 2 | 2026-06 |" in text
    )
    assert "priv" not in text
    lines = text.splitlines()
    tests_at = lines.index("- **Tests**:")
    assert lines[tests_at + 1].startswith("  - pub: static count: lines matching `^")
    assert lines[tests_at + 2].startswith(
        "  - gopub: static count: lines matching `^func"
    )
    assert stats.main(["--config", str(cfg), "--hub", str(hub), "--check"]) == 0


def test_hub_check_stale_leaves_file_untouched(tmp_path, fake_scc):
    cfg, hub = _hub_setup(tmp_path)
    stats.main(["--config", str(cfg), "--hub", str(hub)])
    stale = hub.read_bytes().replace(b"| 2026-06 |", b"| 2025-01 |")
    hub.write_bytes(stale)
    assert stats.main(["--config", str(cfg), "--hub", str(hub), "--check"]) == 1
    assert hub.read_bytes() == stale


def test_hub_without_markers_exits_2(tmp_path, fake_scc, capsys):
    cfg, hub = _hub_setup(tmp_path)
    hub.write_text("# hub, no markers\n")
    assert stats.main(["--config", str(cfg), "--hub", str(hub)]) == 2
    assert hub.read_text() == "# hub, no markers\n"
