#!/usr/bin/env python3
"""
Extract readable prose from LaTeX source files for AI text detection.

Strips LaTeX commands, comments, environments (tables, figures, code listings),
and structural markup, leaving only the prose that a human or AI actually wrote.
This cleaned output can then be fed to analyze.py for statistical analysis.

Usage:
    python extract_latex.py document.tex                     # writes to stdout
    python extract_latex.py document.tex -o prose.txt        # writes to file
    python extract_latex.py document.tex --per-section        # JSON per-section output
    python extract_latex.py document.tex --todo-authors "alice,bob,carol"

The --per-section mode splits on \\section/\\subsection/etc. headings and outputs
a JSON array of {heading, line, word_count, prose} objects, useful for passage-
level AI detection in analyze.py or manual review.
"""

import argparse
import json
import re
import sys


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------

def strip_latex_to_prose(text: str,
                         todo_authors: list[str] | None = None,
                         min_words: int = 0) -> str:
    """Convert LaTeX source to plain prose text.

    Args:
        text: Raw LaTeX source.
        todo_authors: Optional list of \\authorname{...} todo-note commands to
            strip (case-insensitive).  Common in multi-author Cybernetica /
            Eurostat documents.  If None, a generic \\todo{} pattern is still
            removed.
        min_words: Discard the result if it contains fewer than this many words.

    Returns:
        Cleaned prose string, or empty string if below min_words.
    """
    # 1. Trim preamble — only keep the document body
    idx = text.find("\\begin{document}")
    if idx >= 0:
        text = text[idx:]

    # 2. Comments
    text = re.sub(r"(?m)^\s*%.*$", "", text)     # full-line comments
    text = re.sub(r"(?<!\\)%.*", "", text)        # inline comments

    # 3. Todo-note commands (project-specific author macros)
    if todo_authors:
        for name in todo_authors:
            # Match both \name{...} and \Name{...}
            text = re.sub(
                r"\\" + re.escape(name) + r"\{[^}]*\}",
                "", text, flags=re.IGNORECASE,
            )
    # Also strip the standard \todo command from the todonotes package
    text = re.sub(r"\\todo\s*(\[[^\]]*\])?\s*\{[^}]*\}", "", text)

    # 4. Float environments that contain no readable prose
    for env in ["table", "figure", "tikzpicture", "lstlisting", "verbatim",
                "minted", "algorithm", "algorithmic"]:
        text = re.sub(
            r"\\begin\{" + env + r"\}.*?\\end\{" + env + r"\}",
            "", text, flags=re.DOTALL,
        )
    # Tabular / tabularx can also appear outside table floats
    text = re.sub(r"\\begin\{tabular[x]?\}.*?\\end\{tabular[x]?\}",
                  "", text, flags=re.DOTALL)

    # 5. Preserve text content of common inline commands
    for cmd in ["textbf", "textit", "emph", "texttt", "textsf", "textrm",
                "textsc", "underline",
                "gls", "Gls", "glspl", "Glspl", "acrshort", "acrlong"]:
        text = re.sub(r"\\" + cmd + r"\{([^}]*)\}", r"\1", text)

    # 6. Drop cross-reference / citation commands (keep nothing)
    for cmd in ["Cref", "cref", "crefrange", "ref", "eqref", "pageref",
                "label", "cite", "citep", "citet", "autocite",
                "url", "href", "hyperref"]:
        text = re.sub(r"\\" + cmd + r"(\{[^}]*\})+", "", text)

    # 7. Section headings — keep the title text (handle nested commands)
    for cmd in ["chapter", "section", "subsection", "subsubsection",
                "paragraph", "subparagraph", "part"]:
        text = re.sub(
            r"\\" + cmd + r"\*?\{((?:[^{}]|\{[^}]*\})*)\}",
            r"\1", text,
        )

    # 8. Strip list / environment delimiters
    text = re.sub(r"\\begin\{[^}]+\}(\[[^\]]*\])?", "", text)
    text = re.sub(r"\\end\{[^}]+\}", "", text)

    # 9. Item markers
    text = re.sub(r"\\item\[([^\]]*)\]", r"\1", text)
    text = re.sub(r"\\item\b", "", text)

    # 10. Remaining commands — aggressive catch-all
    #     Matches \command, \command{arg}, \command{arg1}{arg2}, etc.
    text = re.sub(r"\\[a-zA-Z@]+\*?(\{[^}]*\})*", "", text)

    # 11. Cleanup
    text = re.sub(r"[{}~]", " ", text)           # braces and ties
    text = re.sub(r"[ \t]+", " ", text)           # collapse horizontal ws
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)  # collapse blank lines
    text = text.strip()

    if min_words and len(text.split()) < min_words:
        return ""
    return text


# ---------------------------------------------------------------------------
# Per-section splitting
# ---------------------------------------------------------------------------

def _balanced_brace_pattern() -> str:
    """Return a regex fragment that matches a balanced {...} group, one level deep."""
    # Matches { ... } where the content can contain nested {subgroup} pairs
    return r"\{(?:[^{}]|\{[^}]*\})*\}"

_HEADING_RE = re.compile(
    r"(\\(?:chapter|section|subsection|subsubsection|paragraph|subparagraph)"
    r"\*?" + _balanced_brace_pattern() + r")"
)


def split_into_sections(text: str,
                        todo_authors: list[str] | None = None,
                        min_words: int = 30) -> list[dict]:
    """Split LaTeX source at heading commands and clean each section.

    Returns a list of dicts:
        {"heading": str, "word_count": int, "prose": str}
    Sections with fewer than *min_words* of prose are dropped.
    """
    # Trim preamble
    idx = text.find("\\begin{document}")
    body = text[idx:] if idx >= 0 else text

    parts = _HEADING_RE.split(body)
    # parts = [pre-text, heading1, text1, heading2, text2, ...]

    sections: list[dict] = []
    for i in range(1, len(parts) - 1, 2):
        heading_raw = parts[i]
        content = parts[i + 1] if i + 1 < len(parts) else ""

        # Extract heading text — handle nested commands like \gls{CTS}
        # Strip the outer \command*{ ... } wrapper, then clean inner commands
        m = re.search(r"\{((?:[^{}]|\{[^}]*\})*)\}", heading_raw)
        heading = m.group(1) if m else heading_raw
        # Strip any remaining \commands inside the heading text
        heading = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", heading)
        heading = heading.strip()

        prose = strip_latex_to_prose(content,
                                     todo_authors=todo_authors,
                                     min_words=0)  # we filter below
        words = prose.split()
        if len(words) < min_words:
            continue

        sections.append({
            "heading": heading,
            "word_count": len(words),
            "prose": prose,
        })

    return sections


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Extract readable prose from LaTeX for AI detection.",
    )
    ap.add_argument("file", help="Path to .tex file")
    ap.add_argument("-o", "--output", default=None,
                    help="Write output to this file (default: stdout)")
    ap.add_argument("--per-section", action="store_true",
                    help="Output JSON array of per-section extracts")
    ap.add_argument("--min-words", type=int, default=30,
                    help="Drop sections with fewer words (per-section mode, "
                         "default: 30)")
    ap.add_argument("--todo-authors", default=None,
                    help="Comma-separated list of \\author{} todo-note "
                         "commands to strip, e.g. 'alice,bob,carol'")

    args = ap.parse_args()

    with open(args.file, "r", encoding="utf-8") as f:
        raw = f.read()

    authors = (
        [a.strip() for a in args.todo_authors.split(",")]
        if args.todo_authors else None
    )

    if args.per_section:
        sections = split_into_sections(raw,
                                        todo_authors=authors,
                                        min_words=args.min_words)
        result = json.dumps(sections, indent=2, ensure_ascii=False)
    else:
        result = strip_latex_to_prose(raw, todo_authors=authors)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        n = len(result.split()) if not args.per_section else sum(
            s["word_count"] for s in sections
        )
        print(f"Wrote {len(result)} chars ({n} words) → {args.output}",
              file=sys.stderr)
    else:
        print(result)


if __name__ == "__main__":
    main()
