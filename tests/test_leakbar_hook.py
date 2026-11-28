"""scripts/check-leakbar.sh — the pre-push leak-bar term check.

Each test builds a throwaway repo in tmp_path, feeds the script git's pre-push
stdin line, and asserts the exit code: hit -> 1, clean -> 0, unset/missing -> 0,
scan error (bad regex, unreadable term file, broken git config) -> 2.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check-leakbar.sh"
ZERO = "0" * 40
TERM = "zorblax"  # fixture term; never a real restricted word


@pytest.fixture
def env(tmp_path: Path) -> dict[str, str]:
    # Isolate from the developer's global/system git config (hooksPath, signing).
    e = dict(os.environ)
    e.update(
        GIT_CONFIG_GLOBAL=str(tmp_path / "gitconfig"),
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@t",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@t",
    )
    return e


def git(repo: Path, env: dict[str, str], *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout.strip()


def commit(
    repo: Path, env: dict[str, str], body: str, msg: str = "c", name: str = "f.txt"
) -> str:
    (repo / name).write_text(body)
    git(repo, env, "add", name)
    git(repo, env, "commit", "-q", "-m", msg)
    return git(repo, env, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path, env: dict[str, str]) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    git(r, env, "init", "-q")
    terms = tmp_path / "terms.re"
    terms.write_text(f"# comment line, ignored\n\n{TERM}\n")
    git(r, env, "config", "leakbar.termsFile", str(terms))
    return r


def run(
    repo: Path,
    env: dict[str, str],
    local: str,
    remote: str = ZERO,
    ref: str = "refs/heads/main",
    args: tuple[str, ...] = (),
):
    stdin = f"{ref} {local} {ref} {remote}\n"
    return subprocess.run(
        [str(SCRIPT), *args],
        cwd=repo,
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
    )


def test_hit_in_patch_blocks(repo, env):
    sha = commit(repo, env, "line with Zorblax inside\n")
    r = run(repo, env, sha)
    assert r.returncode == 1, r.stderr
    assert f"{sha[:7]} c: +line with Zorblax inside" in r.stderr


def test_hit_in_message_only_blocks(repo, env):
    sha = commit(repo, env, "clean body\n", msg=f"subject\n\nmentions {TERM}")
    r = run(repo, env, sha)
    assert r.returncode == 1, r.stderr
    assert f"mentions {TERM}" in r.stderr


def test_clean_range_passes(repo, env):
    sha = commit(repo, env, "nothing to see\n")
    r = run(repo, env, sha)
    assert r.returncode == 0, r.stderr
    assert "leakbar: ok" in r.stderr


def test_hit_before_remote_tip_is_out_of_range(repo, env):
    old = commit(repo, env, f"{TERM} already published\n")
    new = commit(repo, env, "clean follow-up\n", name="g.txt")
    assert run(repo, env, new, remote=old).returncode == 0
    assert run(repo, env, new).returncode == 1  # same commits, new-branch range


def test_scrub_of_published_line_passes(repo, env):
    old = commit(repo, env, f"keep\n{TERM} already published\n")
    new = commit(repo, env, "keep\nscrubbed\n")
    r = run(repo, env, new, remote=old)
    assert r.returncode == 0, r.stderr


def test_unset_key_skips(repo, env):
    sha = commit(repo, env, f"{TERM}\n")
    git(repo, env, "config", "--unset", "leakbar.termsFile")
    r = run(repo, env, sha)
    assert r.returncode == 0
    assert r.stderr.strip().splitlines() == [
        "leakbar: skipped (git config leakbar.termsFile unset or file missing)"
    ]


def test_missing_file_skips(repo, env, tmp_path):
    sha = commit(repo, env, f"{TERM}\n")
    git(repo, env, "config", "leakbar.termsFile", str(tmp_path / "absent.re"))
    r = run(repo, env, sha)
    assert r.returncode == 0
    assert "skipped" in r.stderr


def test_global_key_is_ignored(repo, env, tmp_path):
    # Only the clone's own .git/config may name the term file.
    sha = commit(repo, env, f"{TERM}\n")
    terms = git(repo, env, "config", "--get", "leakbar.termsFile")
    git(repo, env, "config", "--unset", "leakbar.termsFile")
    git(repo, env, "config", "--global", "leakbar.termsFile", terms)
    r = run(repo, env, sha)
    assert r.returncode == 0
    assert "skipped" in r.stderr


# --- fail-open regressions: each of these pushed the term with "leakbar: ok" ---


def test_invalid_regex_blocks(repo, env, tmp_path):
    sha = commit(repo, env, f"{TERM}\n")
    (tmp_path / "terms.re").write_text(f"{TERM}\nbad(\n")
    r = run(repo, env, sha)
    assert r.returncode == 2, r.stderr
    assert "grep failed" in r.stderr


def test_unreadable_term_file_blocks(repo, env, tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root reads mode-000 files")
    sha = commit(repo, env, f"{TERM}\n")
    terms = tmp_path / "terms.re"
    terms.chmod(0)
    try:
        r = run(repo, env, sha)
    finally:
        terms.chmod(0o600)
    assert r.returncode == 2, r.stderr


def test_broken_git_config_blocks(repo, env):
    sha = commit(repo, env, f"{TERM}\n")
    with (repo / ".git" / "config").open("a") as f:
        f.write("[leakbar\n")
    r = run(repo, env, sha)
    assert r.returncode == 2, r.stderr
    assert "git config" in r.stderr


def test_diff_attribute_does_not_hide_patch(repo, env):
    commit(repo, env, "f.txt -diff\n", name=".gitattributes")
    sha = commit(repo, env, f"hidden {TERM}\n")
    r = run(repo, env, sha)
    assert r.returncode == 1, r.stderr
    assert f"+hidden {TERM}" in r.stderr


def test_color_always_does_not_hide_patch(repo, env):
    git(repo, env, "config", "color.ui", "always")
    sha = commit(repo, env, f"colored {TERM}\n")
    r = run(repo, env, sha)
    assert r.returncode == 1, r.stderr
    assert f"+colored {TERM}" in r.stderr


def test_hit_in_author_name_blocks(repo, env):
    e = {**env, "GIT_AUTHOR_NAME": TERM}
    sha = commit(repo, e, "clean body\n")
    r = run(repo, env, sha)
    assert r.returncode == 1, r.stderr
    assert f"{TERM} t@t" in r.stderr


def test_hit_in_annotated_tag_message_blocks(repo, env):
    commit(repo, env, "clean body\n")
    git(repo, env, "tag", "-a", "v1", "-m", f"release {TERM}")
    tag = git(repo, env, "rev-parse", "v1")
    r = run(repo, env, tag, ref="refs/tags/v1")
    assert r.returncode == 1, r.stderr
    assert f"tag refs/tags/v1: release {TERM}" in r.stderr


def two_remotes(repo, env, sha):
    for name in ("origin", "private"):
        git(repo, env, "remote", "add", name, f"https://example.invalid/{name}.git")
    git(repo, env, "update-ref", "refs/remotes/private/main", sha)


@pytest.mark.parametrize("remote", ["origin", "https://example.invalid/origin.git"])
def test_commit_on_other_remote_still_scanned(repo, env, remote):
    sha = commit(repo, env, f"{TERM} only on private\n")
    two_remotes(repo, env, sha)
    r = run(repo, env, sha, args=(remote,))
    assert r.returncode == 1, r.stderr


def test_commit_on_push_remote_is_excluded(repo, env):
    sha = commit(repo, env, f"{TERM} already on origin\n")
    two_remotes(repo, env, sha)
    git(repo, env, "update-ref", "refs/remotes/origin/main", sha)
    new = commit(repo, env, "clean follow-up\n", name="g.txt")
    r = run(repo, env, new, args=("origin",))
    assert r.returncode == 0, r.stderr
