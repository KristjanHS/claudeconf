"""scripts/sync_from_dotfiles.py against a throwaway git repo standing in for dotfiles."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REPO_ROOT

_spec = importlib.util.spec_from_file_location(
    "sync_from_dotfiles", REPO_ROOT / "scripts" / "sync_from_dotfiles.py"
)
assert _spec is not None and _spec.loader is not None
sync = importlib.util.module_from_spec(_spec)
sys.modules["sync_from_dotfiles"] = sync
_spec.loader.exec_module(sync)

TERMS = ["secretco"]
HOME = "/" + "home/alice/"


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def commit(repo: Path, files: dict[str, str], msg: str = "c") -> None:
    for rel, body in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(body)
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", msg)


@pytest.fixture
def repos(tmp_path, monkeypatch):
    dot, root = tmp_path / "dotfiles", tmp_path / "claudeconf"
    root.mkdir()
    git(tmp_path, "init", "-q", str(dot))
    commit(
        dot,
        {
            sync.TERMS: "# comment\nsecretco\n",
            "claude/.claude/rules/a.md": "see ~/x\n",
            "claude/.claude/statusline.sh": "echo hi\n",
            "skills/s1/SKILL.md": "skill\n",
            "skills/s1/ref/r.md": "cites references/unpub.md\n",
            "skills/s2/SKILL.md": "unlisted skill\n",
            "claude/.claude/hooks/new.py": "x = 1\n",
            "claude/.claude/hooks/private.py": "x = 2\n",
        },
    )
    (dot / "claude/.claude/statusline.sh").chmod(0o755)
    git(dot, "update-index", "--chmod=+x", "claude/.claude/statusline.sh")
    git(dot, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x")
    (root / sync.MANIFEST).write_text(
        "# m\n"
        ".claude/rules/a.md <- claude/.claude/rules/a.md\n"
        ".claude/statusline.sh <- claude/.claude/statusline.sh\n"
        ".claude/skills/s1/ <- skills/s1/\n"
    )
    (root / sync.IGNORE).write_text("claude/.claude/hooks/private.py\n")
    monkeypatch.setenv("DOTFILES", str(dot))
    return dot, root


def run(root: Path, *flags: str) -> int:
    return sync.main([*flags, "--root", str(root)])


# --- sanitize -------------------------------------------------------------


@pytest.mark.parametrize(
    ("suffix", "expected"),
    [(".md", "cd ~/proj\n"), (".sh", "cd $HOME/proj\n"), (".txt", "cd ~/proj\n")],
)
def test_home_path_rewritten_per_suffix(suffix, expected):
    assert sync.sanitize(f"cd {HOME}proj\n", suffix, TERMS) == expected


def test_macos_home_path_rewritten():
    assert sync.sanitize("/" + "Users/bob/x\n", ".md", TERMS) == "~/x\n"


def test_home_path_in_python_is_refused():
    with pytest.raises(sync.Refused, match="home path in .py, line 2"):
        sync.sanitize(f"a = 1\nP = '{HOME}x'\n", ".py", TERMS)


def test_email_is_refused():
    with pytest.raises(sync.Refused, match="email"):
        sync.sanitize("mail me: a" + "@example.com\n", ".md", TERMS)


def test_private_term_refused_case_insensitive_word_bounded():
    with pytest.raises(sync.Refused, match="private term 'secretco', line 2"):
        sync.sanitize("ok\nsee SecretCo-plan\n", ".md", TERMS)
    assert sync.sanitize("notsecretco secretcoish\n", ".md", TERMS)


def test_rewrites_apply_before_term_check():
    rewrites = [(sync.re.compile(r"secretco-(\w+)"), r"<private-\1>")]
    assert (
        sync.sanitize("secretco-plan\n", ".md", TERMS, rewrites) == "<private-plan>\n"
    )


# --- engine ---------------------------------------------------------------


def test_sync_writes_manifest_files(repos, capsys):
    _, root = repos
    assert run(root) == 0
    assert (root / ".claude/rules/a.md").read_text() == "see ~/x\n"
    assert (root / ".claude/skills/s1/ref/r.md").is_file()
    assert (root / ".claude/statusline.sh").stat().st_mode & 0o100
    assert "sync: 4 changed, 0 unchanged, 0 refused" in capsys.readouterr().out


def test_second_run_is_idempotent(repos, capsys):
    _, root = repos
    run(root)
    capsys.readouterr()
    assert run(root) == 0
    assert "sync: 0 changed, 4 unchanged, 0 refused" in capsys.readouterr().out


def test_dry_run_writes_nothing(repos, capsys):
    _, root = repos
    assert run(root, "--dry-run") == 0
    assert not (root / ".claude").exists()
    assert "would write .claude/rules/a.md" in capsys.readouterr().out


def test_source_is_head_not_worktree(repos):
    dot, root = repos
    (dot / "claude/.claude/rules/a.md").write_text("uncommitted WIP\n")
    run(root)
    assert (root / ".claude/rules/a.md").read_text() == "see ~/x\n"


def test_dir_mirror_keeps_target_only_extras(repos):
    _, root = repos
    extra = root / ".claude/skills/s1/extra.md"
    extra.parent.mkdir(parents=True)
    extra.write_text("claudeconf-only\n")
    assert run(root) == 0
    assert extra.read_text() == "claudeconf-only\n"


def test_refused_file_is_not_written_and_exits_1(repos, capsys):
    dot, root = repos
    commit(dot, {"claude/.claude/rules/a.md": "from the secretco repo\n"})
    stale = root / ".claude/rules/a.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("stale\n")
    assert run(root) == 1
    assert stale.read_text() == "stale\n"
    assert (
        "REFUSED .claude/rules/a.md: private term 'secretco', line 1"
        in capsys.readouterr().out
    )


def test_missing_terms_file_fails_closed(repos, capsys):
    dot, root = repos
    git(dot, "rm", "-q", sync.TERMS)
    git(dot, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "rm")
    assert run(root) == 1
    assert not (root / ".claude").exists()
    assert "sync: 0 changed, 0 unchanged, 4 refused" in capsys.readouterr().out


def test_never_sync_refuses_even_when_listed(repos, capsys):
    dot, root = repos
    commit(dot, {"claude/.claude/settings.json": "{}\n"})
    with (root / sync.MANIFEST).open("a") as fh:
        fh.write(".claude/settings.json <- claude/.claude/settings.json\n")
    assert run(root) == 1
    assert not (root / ".claude/settings.json").exists()
    assert "REFUSED .claude/settings.json: NEVER_SYNC" in capsys.readouterr().out


def test_missing_source_is_refused(repos, capsys):
    _, root = repos
    with (root / sync.MANIFEST).open("a") as fh:
        fh.write(".claude/rules/gone.md <- claude/.claude/rules/gone.md\n")
    assert run(root) == 1
    assert "REFUSED claude/.claude/rules/gone.md: missing in dotfiles HEAD" in (
        capsys.readouterr().out
    )


def test_proposals_list_unlisted_unignored_paths(repos, capsys):
    _, root = repos
    run(root)
    out = capsys.readouterr().out
    assert "add to manifest? claude/.claude/hooks/new.py" in out
    assert "add to manifest? skills/s2/" in out
    assert "private.py" not in out
    assert "add to manifest? skills/s1/" not in out


def test_dangling_cite_is_advisory(repos, capsys):
    _, root = repos
    assert run(root) == 0
    assert "advisory: dangling cite references/unpub.md" in capsys.readouterr().out


# --- --check --------------------------------------------------------------


def test_check_clean_after_sync(repos, capsys):
    _, root = repos
    run(root)
    capsys.readouterr()
    assert run(root, "--check") == 0
    assert "drift: 0 drifted, 0 held, 0 broken" in capsys.readouterr().out


def test_check_flags_hand_edit(repos, capsys):
    _, root = repos
    run(root)
    with (root / ".claude/rules/a.md").open("a") as fh:
        fh.write("hand edit\n")
    capsys.readouterr()
    assert run(root, "--check") == 1
    assert "DRIFT .claude/rules/a.md" in capsys.readouterr().out


def test_check_held_file_warns_exit_0(repos, capsys):
    dot, root = repos
    run(root)
    commit(dot, {"claude/.claude/rules/a.md": "secretco\n"})
    capsys.readouterr()
    assert run(root, "--check") == 0
    assert "HELD .claude/rules/a.md" in capsys.readouterr().out


def test_check_missing_source_is_drift_not_held(repos, capsys):
    _, root = repos
    run(root)
    with (root / sync.MANIFEST).open("a") as fh:
        fh.write(".claude/rules/gone.md <- claude/.claude/rules/gone.md\n")
    capsys.readouterr()
    assert run(root, "--check") == 1
    assert "REFUSED claude/.claude/rules/gone.md: missing" in capsys.readouterr().out


def test_check_missing_terms_is_drift_not_held(repos, capsys):
    dot, root = repos
    run(root)
    git(dot, "rm", "-q", sync.TERMS)
    git(dot, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "rm")
    capsys.readouterr()
    assert run(root, "--check") == 1
    assert "0 held, 4 broken" in capsys.readouterr().out


def test_check_skips_without_dotfiles(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DOTFILES", str(tmp_path / "nonexistent"))
    assert run(tmp_path, "--check") == 0
    assert "drift: skipped" in capsys.readouterr().out


def test_real_manifest_parses():
    pairs = sync.parse_manifest(REPO_ROOT)
    dsts = [d for d, _ in pairs]
    assert len(dsts) == len(set(dsts))
    assert not set(dsts) & sync.NEVER_SYNC
