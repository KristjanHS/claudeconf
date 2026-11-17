"""Every `#anchor` and relative link in README.md, ADOPT.md and docs/*.md must resolve on GitHub.

Also: every dated `YYYY-MM-DD-<name>.md` cited in any tracked file names a tracked file,
apart from the pinned DANGLING_BASELINE.
"""

from __future__ import annotations

import html
import re
import subprocess
import unicodedata
from pathlib import Path
from urllib.parse import unquote

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")
INLINE_LINK = re.compile(
    r"""\]\(\s*(?:<([^>\n]*)>|([^)\s]+))(?:\s+(?:"[^"]*"|'[^']*'|\([^)]*\)))?\s*\)"""
)
REF_DEF = re.compile(r"^\s*\[[^\]]+\]:\s*<?(\S+?)>?(?:\s|$)")
HTML_REF = re.compile(r"""(?:href|src)=["']([^"']+)["']""")
HTML_ANCHOR = re.compile(r"""<[a-z]+[^>]*\s(?:id|name)=["']([^"']+)["']""", re.I)
INLINE_CODE = re.compile(r"(`+)(.+?)(?<!`)\1(?!`)")
EXTERNAL = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)


def doc_files() -> list[Path]:
    return [
        REPO_ROOT / "README.md",
        REPO_ROOT / "ADOPT.md",
        *sorted((REPO_ROOT / "docs").glob("*.md")),
    ]


def prose_lines(text: str):
    fence = ""
    for n, line in enumerate(text.splitlines(), 1):
        m = FENCE.match(line)
        if fence:
            if (
                m
                and m[1][0] == fence[0]
                and len(m[1]) >= len(fence)
                and not m[2].strip()
            ):
                fence = ""
        elif m:
            fence = m[1]
        else:
            yield n, line


def slugify(heading: str) -> str:
    codes: list[str] = []
    text = INLINE_CODE.sub(
        lambda m: f"\0{codes.append(m[2]) or len(codes) - 1}\0", heading
    )
    text = re.sub(r"!?\[([^\]]*)\](?:\([^)]*\)|\[[^\]]*\])", r"\1", text)
    text = re.sub(r"(?<!\w)[*_]+|[*_]+(?!\w)", "", text)
    text = html.unescape(re.sub(r"<[^<>\0]+>", "", text))
    text = re.sub(r"\0(\d+)\0", lambda m: codes[int(m[1])], text).lower()
    keep = (c for c in text if c in "_- " or unicodedata.category(c)[0] in "LMN")
    return "".join(keep).replace(" ", "-")


def anchors(path: Path) -> set[str]:
    seen: dict[str, int] = {}
    out: set[str] = set()
    for _, line in prose_lines(path.read_text(encoding="utf-8")):
        out.update(HTML_ANCHOR.findall(INLINE_CODE.sub("", line)))
        m = HEADING.match(line)
        if m:
            slug = slugify(m.group(1))
            count = seen.get(slug, 0)
            seen[slug] = count + 1
            out.add(slug if count == 0 else f"{slug}-{count}")
    return out


def broken_links(path: Path, root: Path = REPO_ROOT) -> list[str]:
    problems: list[str] = []
    own = anchors(path)
    for n, line in prose_lines(path.read_text(encoding="utf-8")):
        line = INLINE_CODE.sub("", line)
        targets = [a or b for a, b in INLINE_LINK.findall(line)]
        targets += REF_DEF.findall(line) + HTML_REF.findall(line)
        for target in targets:
            if EXTERNAL.match(target):
                continue
            ref, _, frag = target.partition("#")
            frag = unquote(frag)
            where = f"{path.name}:{n}: {target}"
            if not ref:
                if frag not in own:
                    problems.append(f"{where} — no such heading")
                continue
            dest = (path.parent / unquote(ref)).resolve()
            if not dest.is_relative_to(root.resolve()):
                problems.append(f"{where} — outside the repo")
            elif not dest.exists():
                problems.append(f"{where} — missing file")
            elif frag and dest.suffix == ".md" and frag not in anchors(dest):
                problems.append(f"{where} — no such heading in {dest.name}")
    return problems


@pytest.mark.parametrize(
    "doc", doc_files(), ids=lambda p: p.relative_to(REPO_ROOT).as_posix()
)
def test_doc_links_resolve(doc: Path) -> None:
    assert broken_links(doc) == []


@pytest.mark.parametrize(
    ("heading", "slug"),
    [
        ("🚀 Quick start", "-quick-start"),
        ("Does this actually work?", "does-this-actually-work"),
        (
            "The budget governor — `impag-budget-check.py`",
            "the-budget-governor--impag-budget-checkpy",
        ),
        ("When this isn't worth it", "when-this-isnt-worth-it"),
        ("⚠️ Warning", "\ufe0f-warning"),
        ("Cafe\u0301 decomposed", "cafe\u0301-decomposed"),
        ("Using _emphasis_ here", "using-emphasis-here"),
        ("Under_score in `snake_case`", "under_score-in-snake_case"),
        ("Using `<details>` blocks", "using-details-blocks"),
        ("Rules &amp; gates", "rules--gates"),
        ("&lt;b&gt; tag", "b-tag"),
        ("See [the docs][ref]", "see-the-docs"),
    ],
)
def test_slugify_matches_github(heading: str, slug: str) -> None:
    assert slugify(heading) == slug


def test_planted_breakage_is_reported(tmp_path: Path) -> None:
    (tmp_path / "other.md").write_text("# Other\n## Dup\n## Dup\n", encoding="utf-8")
    doc = tmp_path / "doc.md"
    doc.write_text(
        "# Real heading\n"
        "[ok](#real-heading) [ok](other.md#dup-1) [ok](https://example.com/#x)\n"
        "[bad](#-no-such-heading)\n"
        "[bad](missing.md)\n"
        "[bad](other.md#nope)\n"
        "[bad](../escape.md)\n"
        "[r]: missing2.md\n"
        '<img src="missing3.png">\n'
        '<a id="x"></a> [ok](#x) [ok](other%2Emd)\n'
        "```\n[ignored](#inside-a-fence)\n```\n"
        "`[ignored](#inside-code)`\n",
        encoding="utf-8",
    )
    (tmp_path.parent / "escape.md").touch()
    problems = broken_links(doc, root=tmp_path)
    assert [p.split(": ", 1)[1] for p in problems] == [
        "#-no-such-heading — no such heading",
        "missing.md — missing file",
        "other.md#nope — no such heading in other.md",
        "../escape.md — outside the repo",
        "missing2.md — missing file",
        "missing3.png — missing file",
    ]


@pytest.mark.parametrize(
    ("body", "problem"),
    [
        ("```\n~~~\n```\n[x](#nope)", "#nope — no such heading"),
        ("````\n```\n````\n[x](#nope)", "#nope — no such heading"),
        ("~~~\n```\n~~~\n[x](#nope)", "#nope — no such heading"),
        ("```\n```py\n```\n[x](#nope)", "#nope — no such heading"),
        ("para\n\n    ```\n[x](#nope)", "#nope — no such heading"),
        ("[x](#nope 'title')", "#nope — no such heading"),
        ("[x](#nope (title))", "#nope — no such heading"),
        ("[x](<no such.md>)", "no such.md — missing file"),
        ('`<a id="fake">`\n[x](#fake)', "#fake — no such heading"),
    ],
)
def test_link_form_is_parsed(tmp_path: Path, body: str, problem: str) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text(body + "\n", encoding="utf-8")
    assert [p.split(": ", 1)[1] for p in broken_links(doc, root=tmp_path)] == [problem]


DATED_CITE = re.compile(r"\d{4}-\d{2}-\d{2}-[\w.-]+\.md")
# Dated docs cited here that live only in the author's dotfiles, never in this repo.
# Pinned so any NEW unresolved cite fails; drop an entry once its cite is gone.
# Stems, not `.md` names: a literal name here would cite itself and never go stale.
DANGLING_BASELINE = frozenset(
    {
        "2026-04-18-precompact-hook-design",
        "2026-08-09-session-token-audit-round-2",
        "2026-09-27-security-critique-todo",
    }
)


def tracked_files(root: Path = REPO_ROOT) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True,
        capture_output=True,
    ).stdout.decode()
    # Index entries deleted in the working tree count as gone (a pending removal).
    return [p for p in out.split("\0") if p and (root / p).is_file()]


def dangling_cites(root: Path, files: list[str]) -> dict[str, list[str]]:
    """Map each cited dated `.md` name no file in `files` carries to its `path:line` sites."""
    names = {Path(p).name for p in files}
    out: dict[str, list[str]] = {}
    for rel in files:
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for cite in DATED_CITE.findall(line):
                if cite not in names:
                    out.setdefault(cite, []).append(f"{rel}:{n}")
    return out


def test_dated_cites_resolve() -> None:
    dangling = {
        k.removesuffix(".md"): v
        for k, v in dangling_cites(REPO_ROOT, tracked_files()).items()
    }
    new = {k: v for k, v in dangling.items() if k not in DANGLING_BASELINE}
    assert new == {}, "cited dated doc is not a tracked file"
    stale = DANGLING_BASELINE - dangling.keys()
    assert not stale, "baseline entry no longer dangles — remove it"


def test_planted_dangling_cite_is_reported(tmp_path: Path) -> None:
    # Names are assembled so this file never cites them literally (the guard scans it).
    day = "2026-01-0"
    here, gone, binary = f"{day}1-here.md", f"{day}2-gone.md", f"{day}3-binary.md"
    (tmp_path / here).write_text("x\n", encoding="utf-8")
    (tmp_path / "a.py").write_text(
        f"# see docs/{here}\n# see {gone}\n", encoding="utf-8"
    )
    (tmp_path / "b.bin").write_bytes(b"\xff" + binary.encode())
    files = [here, "a.py", "b.bin"]
    assert dangling_cites(tmp_path, files) == {gone: ["a.py:2"]}
