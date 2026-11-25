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
    git(tmp_path, "init", "-q", str(root))
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
    assert (
        "sync: 4 changed, 0 unchanged, 0 refused, 0 deleted" in capsys.readouterr().out
    )


def test_second_run_is_idempotent(repos, capsys):
    _, root = repos
    run(root)
    capsys.readouterr()
    assert run(root) == 0
    assert (
        "sync: 0 changed, 4 unchanged, 0 refused, 0 deleted" in capsys.readouterr().out
    )


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


def test_dir_mirror_deletes_tracked_files_whose_source_is_gone(repos, capsys):
    _, root = repos
    commit(root, {".claude/skills/s1/old/extra.md": "x\n", ".gitignore": "*.pyc\n"})
    orphan = root / ".claude/skills/s1/old/extra.md"
    ignored = root / ".claude/skills/s1/x.pyc"
    ignored.write_text("x\n")
    assert run(root, "--dry-run") == 0
    assert orphan.is_file()
    assert "would delete .claude/skills/s1/old/extra.md" in capsys.readouterr().out
    assert run(root) == 0
    assert not orphan.parent.exists()
    assert ignored.is_file()
    assert (root / ".claude/skills/s1/SKILL.md").is_file()
    assert "1 deleted" in capsys.readouterr().out


def test_untracked_orphan_is_refused_not_deleted(repos, capsys):
    _, root = repos
    draft = root / ".claude/skills/s1/notes.md"
    draft.parent.mkdir(parents=True)
    draft.write_text("wip\n")
    assert run(root) == 1
    assert draft.is_file()
    assert "REFUSED .claude/skills/s1/notes.md: untracked" in capsys.readouterr().out


def test_missing_source_dir_keeps_mirror(repos):
    dot, root = repos
    run(root)
    commit(root, {})
    git(dot, "rm", "-rq", "skills/s1")
    git(dot, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "rm")
    assert run(root) == 1
    assert (root / ".claude/skills/s1/SKILL.md").is_file()


def test_refused_mirror_file_is_held_not_deleted(repos):
    dot, root = repos
    run(root)
    commit(dot, {"skills/s1/ref/r.md": "secretco\n"})
    assert run(root) == 1
    assert (root / ".claude/skills/s1/ref/r.md").is_file()


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
    assert (
        "sync: 0 changed, 0 unchanged, 4 refused, 0 deleted" in capsys.readouterr().out
    )


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


def test_check_flags_orphan_without_deleting(repos, capsys):
    _, root = repos
    run(root)
    orphan = root / ".claude/skills/s1/extra.md"
    orphan.write_text("stale\n")
    capsys.readouterr()
    assert run(root, "--check") == 1
    assert "ORPHAN .claude/skills/s1/extra.md" in capsys.readouterr().out
    assert orphan.is_file()


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


# --- --candidates ---------------------------------------------------------


def cand(root: Path, capsys) -> str:
    assert run(root, "--candidates") == 0
    return capsys.readouterr().out


def row(path: str, kind: str, size: int, summary: str, hit: str = "n") -> str:
    return f"| `{path}` | {kind} | {size} | {summary} | {hit} | |"


def test_candidates_exact_table(repos, capsys):
    dot, root = repos
    files = {
        "claude/.claude/hooks/new.py": '#!/usr/bin/env python3\n# note\n"""\nNew hook.\n"""\n',
        "skills/s2/SKILL.md": '---\nname: s2\ndescription: "Second skill."\n---\n# S2\n',
        "skills/s2/ref.md": "extra\n",
        "claude/.claude/references/r.md": "# Ref title\nbody\n",
        "claude/.claude/commands/c.md": "intro\n## Cmd heading\n",
    }
    commit(dot, files)
    s2 = len(files["skills/s2/SKILL.md"]) + len(files["skills/s2/ref.md"])

    def size(rel: str) -> int:
        return len(files["claude/.claude/" + rel])

    assert cand(root, capsys).splitlines() == [
        *sync.CANDIDATE_HEADER.splitlines(),
        row(
            "claude/.claude/commands/c.md",
            "command",
            size("commands/c.md"),
            "Cmd heading",
        ),
        row("claude/.claude/hooks/new.py", "hook", size("hooks/new.py"), "New hook."),
        row(
            "claude/.claude/references/r.md",
            "reference",
            size("references/r.md"),
            "Ref title",
        ),
        row("skills/s2/", "skill", s2, "Second skill."),
        "",
        "candidates: 4 rows, 0 withheld",
    ]


def test_candidates_private_term_description_withheld(repos, capsys):
    dot, root = repos
    body = "---\ndescription: SecretCo helper\n---\n"
    commit(dot, {"skills/s2/SKILL.md": body})
    out = cand(root, capsys)
    assert row("skills/s2/", "skill", len(body), "[withheld]", "Y") in out
    assert "secretco" not in out.lower()
    assert "(private term 1)" in out


def test_candidates_term_in_body_only_still_withheld(repos, capsys):
    dot, root = repos
    commit(
        dot, {"skills/s2/SKILL.md": "# Fine title\n", "skills/s2/x.md": "secretco\n"}
    )
    out = cand(root, capsys)
    assert row("skills/s2/", "skill", 22, "[withheld]", "Y") in out
    assert "Fine title" not in out


def test_candidates_term_cleared_by_rewrite_is_n(repos, capsys):
    dot, root = repos
    body = "# SecretCo's plan\n"
    commit(
        dot,
        {sync.REWRITES: "(?i)secretco\tprivate-app\n", "skills/s2/SKILL.md": body},
    )
    assert row("skills/s2/", "skill", len(body), "private-app's plan") in cand(
        root, capsys
    )


@pytest.mark.parametrize(
    ("summary", "category"),
    [
        (f"see {HOME}x", "home path"),
        ("mail a" + "@example.com", "email"),
        ("we Folded it", "fold wording"),
    ],
)
def test_candidates_exposing_summary_withheld(repos, capsys, summary, category):
    dot, root = repos
    body = f"# {summary}\n"
    commit(dot, {"claude/.claude/references/r.md": body})
    out = cand(root, capsys)
    assert (
        row("claude/.claude/references/r.md", "reference", len(body), "[withheld]")
        in out
    )
    assert summary not in out
    assert f"({category} 1)" in out


def test_candidates_private_term_in_path_withholds_path(repos, capsys):
    dot, root = repos
    commit(dot, {"claude/.claude/rules/secretco-x.md": "# t\n"})
    out = cand(root, capsys)
    assert row("[withheld]", "rule", 4, "[withheld]") in out
    assert "secretco" not in out.lower()


def test_candidates_summary_cut_and_pipe_escaped(repos, capsys):
    dot, root = repos
    commit(
        dot,
        {"skills/s2/SKILL.md": "---\ndescription: >-\n  a|b " + "x" * 100 + "\n---\n"},
    )
    summary = cand(root, capsys).split("`skills/s2/` | skill | ")[1].split(" | ")[1]
    assert summary.startswith("a\\|b x")
    assert (
        summary.endswith("…") and len(summary.replace("\\|", "|")) == sync.SUMMARY_MAX
    )


def test_candidates_missing_terms_fail_closed(repos, capsys):
    dot, root = repos
    commit(dot, {"skills/s2/SKILL.md": "# Visible?\n"})
    git(dot, "rm", "-q", sync.TERMS)
    git(dot, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "rm")
    out = cand(root, capsys)
    assert "Visible?" not in out
    assert row("[withheld]", "skill", 11, "[withheld]", "?") in out


def test_candidates_is_read_only(repos, capsys):
    dot, root = repos
    before = sorted(p.relative_to(root) for p in root.rglob("*"))
    cand(root, capsys)
    assert sorted(p.relative_to(root) for p in root.rglob("*")) == before
    status = subprocess.run(
        ["git", "-C", str(dot), "status", "--porcelain"], capture_output=True, text=True
    )
    assert status.stdout == ""


def test_live_manifest_publishes_the_minimal_statusline_not_the_private_one():
    pairs = dict(sync.parse_manifest(REPO_ROOT))
    assert pairs[".claude/statusline.sh"] == sync.PUBLIC_STATUSLINE
