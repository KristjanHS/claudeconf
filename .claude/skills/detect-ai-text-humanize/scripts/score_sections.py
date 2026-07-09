#!/usr/bin/env python3
"""
Per-section AI pattern scoring for AI text detection.

Scores each section of a document for AI writing tells — vocabulary patterns,
structural patterns, formatting tells, and statistical anomalies.  Outputs a
ranked list so the user can focus review on the most AI-sounding passages.

This is the pattern-matching layer (SKILL.md Steps 2 + 4).  It complements
analyze.py (Step 1, whole-document statistical features) and uses
extract_latex.py (Step 0) for LaTeX preprocessing.

Usage:
    # From pre-extracted JSON (output of extract_latex.py --per-section):
    python score_sections.py sections.json

    # Directly from a .tex file (runs extract_latex.py internally):
    python score_sections.py document.tex --todo-authors "alice,bob"

    # Limit output and add custom domain jargon as human markers:
    python score_sections.py sections.json --top 10 --domain-jargon "etcd,SecreC,SPDZ"

    # Machine-readable JSON output:
    python score_sections.py sections.json --json
"""

import argparse
import json
import math
import os
import re
import sys

# ---------------------------------------------------------------------------
# Import sibling modules (analyze.py, extract_latex.py) from the same dir
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

try:
    from analyze import compute_stats, count_ai_vocabulary, check_avoided_words
    _HAS_ANALYZE = True
except ImportError:
    _HAS_ANALYZE = False

try:
    from extract_latex import split_into_sections
    _HAS_EXTRACT = True
except ImportError:
    _HAS_EXTRACT = False


# ---------------------------------------------------------------------------
# AI Pattern Registry
# ---------------------------------------------------------------------------
# Each entry: (regex_pattern, label, category, weight_per_hit, max_weight)
# Weight_per_hit and max_weight control how much a single pattern contributes.
# Categories align with the pattern families in claude-opus-patterns.md.

AI_PATTERNS: list[tuple[str, str, str, int, int]] = [
    # --- Claude vocabulary: hedging ---
    (r"it'?s worth noting",          "Hedge: worth noting",        "vocabulary",  3, 6),
    (r"\bthat said\b",               "Hedge: that said",           "vocabulary",  3, 6),
    (r"\bthat being said\b",         "Hedge: that being said",     "vocabulary",  3, 6),
    (r"\bto be fair\b",              "Hedge: to be fair",          "vocabulary",  3, 6),
    (r"it'?s important to",          "Hedge: important to",        "vocabulary",  3, 6),
    (r"\bgenerally\b",               "Hedge: generally",           "vocabulary",  2, 4),
    (r"\btypically\b",               "Hedge: typically",           "vocabulary",  2, 4),
    (r"\bin many cases\b",           "Hedge: in many cases",       "vocabulary",  3, 6),

    # --- Claude vocabulary: significance inflation ---
    (r"\bpivotal\b",                 "Significance: pivotal",      "vocabulary",  3, 6),
    (r"\bcrucial\b",                 "Significance: crucial",      "vocabulary",  2, 4),
    (r"\bfundamentally\b",           "Significance: fundamentally","vocabulary",  3, 6),
    (r"\bat its core\b",             "Significance: at its core",  "vocabulary",  3, 6),
    (r"\bkey (?:consideration|insight)\b", "Key consideration/insight", "vocabulary", 3, 6),

    # --- Claude vocabulary: AI-typical words ---
    (r"\bcomprehensive(?:ly)?\b",    "AI vocab: comprehensive",    "vocabulary",  2, 4),
    (r"\brobust(?:ness)?\b",         "AI vocab: robust",           "vocabulary",  2, 4),
    (r"\bencompasses\b",             "AI vocab: encompasses",      "vocabulary",  3, 6),
    (r"\bleverag\w+\b",              "AI vocab: leverage",         "vocabulary",  3, 6),
    (r"\blandscape\b",               "AI vocab: landscape",        "vocabulary",  3, 6),
    (r"\bnuanc\w+\b",                "AI vocab: nuanced",          "vocabulary",  3, 6),
    (r"\bholistic(?:ally)?\b",       "AI vocab: holistic",         "vocabulary",  3, 6),
    (r"\bmultifaceted\b",            "AI vocab: multifaceted",     "vocabulary",  4, 4),
    (r"\bfoster(?:s|ing|ed)?\b",     "AI vocab: fostering",        "vocabulary",  3, 6),
    (r"\bundersco\w+\b",             "AI vocab: underscoring",     "vocabulary",  3, 6),
    (r"\bdelve\b",                   "AI vocab: delve",            "vocabulary",  4, 4),
    (r"\btapestry\b",                "AI vocab: tapestry",         "vocabulary",  4, 4),
    (r"\bnavigate(?:s|ing|ed)?\b",   "AI vocab: navigating",       "vocabulary",  2, 4),

    # --- Claude vocabulary: connective meta-commentary ---
    (r"\blet me\b",                  "Meta: let me",               "vocabulary",  3, 6),
    (r"\bhere'?s the thing\b",       "Meta: here's the thing",     "vocabulary",  3, 6),
    (r"\bthe key insight is\b",      "Meta: key insight is",       "vocabulary",  4, 4),
    (r"\bzooming out\b",             "Meta: zooming out",          "vocabulary",  4, 4),
    (r"\btaking a step back\b",      "Meta: taking a step back",   "vocabulary",  4, 4),
    (r"\bbuilding on this\b",        "Meta: building on this",     "vocabulary",  3, 6),
    (r"\bwith that context\b",       "Meta: with that context",    "vocabulary",  4, 4),

    # --- Structural: constructive reframing ---
    (r"\brather than\b",             "Reframing: rather than",     "structure",   1, 4),
    (r"\ba more effective approach\b","Reframing: more effective",  "structure",   4, 4),

    # --- Structural: hedging connectors ---
    (r"\bhowever\b",                 "However (hedging connector)", "structure",  1, 4),

    # --- Structural: self-referential metadiscourse ---
    (r"\bthis (?:section|chapter|document)\b",
                                     "Self-ref: this section/chapter", "structure", 2, 6),

    # --- Structural: preemptive objection handling ---
    (r"\byou might wonder\b",       "Preemptive objection",        "structure",  4, 8),
    (r"\bone (?:reasonable |natural )?(?:concern|objection)\b",
                                     "Preemptive objection",        "structure",  4, 8),

    # --- Structural: parallel enumeration ---
    (r"(?:first|second|third)(?:ly)?[,.]",
                                     "Parallel enumeration",        "structure",  2, 6),

    # --- Formatting: em-dash ---
    (r"—|---",                       "Em-dash usage",               "formatting", 1, 6),

    # --- Formatting: colon introduction ---
    (r":\s*\n",                      "Colon-intro before list/para","formatting", 2, 6),

    # --- Reasoning: caveat sandwich ---
    # Single-sentence check: "although X, however Y" patterns
    (r"\b(?:while|although|even though)\b[^.]{10,}\b(?:however|nevertheless|nonetheless)\b",
                                     "Caveat sandwich",            "reasoning",   4, 8),
]


# Phrases that indicate human authorship (reduce score)
HUMAN_MARKERS: list[tuple[str, str, int]] = [
    (r"\bactually\b",    "Colloquial: actually",   -2),
    (r"\bI think\b",     "First person: I think",  -3),
    (r"\bkind of\b",     "Colloquial: kind of",    -3),
    (r"\bsort of\b",     "Colloquial: sort of",    -3),
    (r"\bstuff\b",       "Colloquial: stuff",      -3),
    (r"\bguess\b",       "Colloquial: guess",      -2),
    (r"\bhonestly\b",    "Avoided-by-Claude: honestly", -3),
    (r"\bgenuinely\b",   "Avoided-by-Claude: genuinely", -3),
    (r"\bstraightforward\b", "Avoided-by-Claude: straightforward", -3),
    (r"\bAnd\s",         "Sentence-initial And",   -1),
    (r"\bBut\s",         "Sentence-initial But",   -1),
]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _sentence_length_std(text: str) -> float | None:
    """Return std dev of sentence lengths, or None if too few sentences."""
    sents = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    sents = [s for s in sents if len(s.split()) >= 3]
    if len(sents) < 3:
        return None
    lens = [len(s.split()) for s in sents]
    avg = sum(lens) / len(lens)
    return math.sqrt(sum((l - avg) ** 2 for l in lens) / len(lens))


def score_section(section: dict,
                  domain_jargon: list[str] | None = None) -> dict:
    """Score a single section for AI tells.

    Expects a dict with at least {"heading": str, "word_count": int, "prose": str}.
    Mutates and returns the dict with added keys:
        ai_score, ai_score_normalized, triggers, categories_hit, stats (if available).
    """
    text = section["prose"]
    wc = section["word_count"]
    score = 0
    triggers: list[str] = []
    categories: set[str] = set()

    # --- Pattern matching ---
    for pattern, label, category, weight, maxw in AI_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        n = len(matches)
        if n > 0:
            pts = min(n * weight, maxw)
            score += pts
            triggers.append(f"{label} (x{n}, +{pts})")
            categories.add(category)

    # --- Human markers (negative score) ---
    for pattern, label, adj in HUMAN_MARKERS:
        n = len(re.findall(pattern, text))
        if n > 0:
            score += adj * n   # adj is already negative
            triggers.append(f"{label} (x{n}, {adj * n})")

    # --- Domain jargon used without explanation = human marker ---
    if domain_jargon:
        jargon_re = r"\b(?:" + "|".join(re.escape(j) for j in domain_jargon) + r")\b"
        found = set(re.findall(jargon_re, text))
        if found:
            adj = -2 * len(found)
            score += adj
            triggers.append(f"Unexplained domain jargon ({', '.join(sorted(found))}, {adj})")

    # --- Sentence-level statistics ---
    sent_std = _sentence_length_std(text)
    if sent_std is not None:
        if sent_std < 6:
            score += 5
            triggers.append(f"Low sentence variance (std={sent_std:.1f}, +5)")
        elif sent_std < 8:
            score += 2
            triggers.append(f"Moderate sentence variance (std={sent_std:.1f}, +2)")

    # --- Paragraph uniformity ---
    paras = [p.strip() for p in text.split("\n\n")
             if p.strip() and len(p.split()) > 10]
    if len(paras) >= 3:
        para_lens = [len(re.split(r"(?<=[.!?])\s+(?=[A-Z])", p)) for p in paras]
        if all(2 <= l <= 6 for l in para_lens):
            score += 5
            triggers.append("Uniform paragraph length (all 2-6 sentences, +5)")

    # --- Per-section stats from analyze.py (if available) ---
    stats_dict = None
    if _HAS_ANALYZE and wc >= 30:
        try:
            stats = compute_stats(text)
            stats_dict = stats._asdict()
            ai_vocab = count_ai_vocabulary(text)
            if ai_vocab:
                # Don't double-count words already in AI_PATTERNS; just note them
                stats_dict["ai_vocabulary"] = ai_vocab
        except Exception:
            pass

    # --- Normalize ---
    normalized = score / (wc / 100) if wc > 0 else 0

    section["ai_score"] = score
    section["ai_score_normalized"] = round(normalized, 2)
    section["triggers"] = triggers
    section["categories_hit"] = sorted(categories)
    if stats_dict:
        section["stats"] = stats_dict

    return section


# ---------------------------------------------------------------------------
# Cross-section analysis: template parallelism
# ---------------------------------------------------------------------------

def detect_template_parallelism(sections: list[dict]) -> list[str]:
    """Find groups of sections with suspiciously similar structure.

    Checks for:
      1. Repeated headings (e.g. 4x "Acceptance criteria", 4x "System under test")
      2. Sections that open with the same phrasing pattern
      3. Shared stock phrases across multiple sections

    Returns a list of human-readable warnings.
    """
    warnings: list[str] = []

    # --- 1. Repeated headings ---
    heading_counts: dict[str, int] = {}
    for sec in sections:
        h = sec["heading"].strip().rstrip(".")
        heading_counts[h] = heading_counts.get(h, 0) + 1
    for h, n in heading_counts.items():
        if n >= 3:
            warnings.append(
                f"Repeated heading: \"{h}\" appears {n} times — "
                f"suggests templated parallel structure"
            )

    # --- 2. Similar opening sentences ---
    openers: list[tuple[str, str]] = []
    for sec in sections:
        prose = sec["prose"].strip()
        m = re.match(r"([^.!?]+[.!?])", prose)
        if m:
            openers.append((sec["heading"], m.group(1).strip()))

    def _skeleton(sent: str) -> str:
        """Reduce sentence to structural skeleton for comparison."""
        s = sent.lower()
        s = re.sub(r"\b(?:tc-?\d|uc-?\d\w?|p\d\.\d)\b", "TCREF", s)
        s = re.sub(r"\b(?:section|chapter|cref|ref)\b", "REF", s)
        words = s.split()[:8]
        return " ".join(words)

    skeletons: dict[str, list[str]] = {}
    for heading, opener in openers:
        skel = _skeleton(opener)
        skeletons.setdefault(skel, []).append(heading)

    for skel, headings in skeletons.items():
        if len(headings) >= 3:
            warnings.append(
                f"Opening parallelism: {len(headings)} sections share opener "
                f"structure — {', '.join(headings[:5])}"
                + (f" (+{len(headings)-5} more)" if len(headings) > 5 else "")
            )

    # --- 3. Shared stock phrases across sections ---
    # Look for identical multi-word phrases that appear in 3+ sections
    stock_phrases = [
        r"the test (?:passes|verifies|checks|succeeds) when",
        r"acceptance criteria (?:are |is )?derived from",
        r"this test case\b.{0,20}\bassesses\b",
        r"the prototype (?:replaces|simplifies|mocks)",
        r"out of scope for (?:the|this) (?:prototype|deliverable)",
        r"in (?:the|a) production system",
    ]
    for phrase_re in stock_phrases:
        matching = [sec["heading"] for sec in sections
                    if re.search(phrase_re, sec["prose"], re.IGNORECASE)]
        if len(matching) >= 3:
            # Extract the actual matched text from one instance for the label
            for sec in sections:
                m = re.search(phrase_re, sec["prose"], re.IGNORECASE)
                if m:
                    example = m.group(0)
                    break
            warnings.append(
                f"Stock phrase \"{example}\" found in {len(matching)} sections: "
                f"{', '.join(matching[:5])}"
            )

    return warnings


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------

def load_sections(path: str,
                  todo_authors: list[str] | None = None,
                  min_words: int = 30) -> list[dict]:
    """Load sections from a JSON file or a .tex file."""
    if path.endswith(".json"):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    if path.endswith(".tex"):
        if not _HAS_EXTRACT:
            print("ERROR: extract_latex.py not found in the same directory. "
                  "Either place it alongside score_sections.py, or pre-extract "
                  "with: python extract_latex.py doc.tex --per-section -o sections.json",
                  file=sys.stderr)
            sys.exit(1)
        return split_into_sections(
            open(path, "r", encoding="utf-8").read(),
            todo_authors=todo_authors,
            min_words=min_words,
        )

    # Try treating it as plain text — split on blank lines
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    sections = []
    for i, p in enumerate(paras):
        words = p.split()
        if len(words) >= min_words:
            sections.append({
                "heading": f"Paragraph {i+1}",
                "word_count": len(words),
                "prose": p,
            })
    return sections


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def print_report(sections: list[dict],
                 parallelism_warnings: list[str],
                 top_n: int = 15) -> None:
    """Print a human-readable ranked report."""
    print("=" * 78)
    print("PER-SECTION AI PATTERN ANALYSIS")
    print("=" * 78)

    if parallelism_warnings:
        print("\n⚠ CROSS-SECTION WARNINGS:")
        for w in parallelism_warnings:
            print(f"  • {w}")

    shown = sections[:top_n]
    print(f"\nTop {len(shown)} sections by normalized AI score:\n")

    for i, sec in enumerate(shown):
        h = sec["heading"]
        raw = sec["ai_score"]
        norm = sec["ai_score_normalized"]
        wc = sec["word_count"]
        cats = ", ".join(sec.get("categories_hit", []))
        print(f"  #{i+1}  [{norm:>6.1f}]  {h}")
        print(f"       {wc} words | raw={raw} | categories: {cats or 'none'}")
        for t in sec.get("triggers", []):
            print(f"         → {t}")
        preview = sec["prose"][:140].replace("\n", " ")
        print(f"         \"{preview}...\"")
        print()

    remaining = len(sections) - top_n
    if remaining > 0:
        print(f"  ... {remaining} more sections below threshold (use --top to see more)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Score document sections for AI writing patterns.",
    )
    ap.add_argument("file",
                    help="Input file: .json (from extract_latex.py --per-section), "
                         ".tex (LaTeX source), or .txt (plain text)")
    ap.add_argument("--top", type=int, default=15,
                    help="Show top N sections (default: 15)")
    ap.add_argument("--min-words", type=int, default=30,
                    help="Skip sections shorter than this (default: 30)")
    ap.add_argument("--todo-authors", default=None,
                    help="For .tex input: comma-separated \\author{} todo-note "
                         "commands to strip")
    ap.add_argument("--domain-jargon", default=None,
                    help="Comma-separated domain terms that act as human markers "
                         "(e.g. 'etcd,SecreC,SPDZ,Rego')")
    ap.add_argument("--json", action="store_true",
                    help="Output machine-readable JSON instead of report")

    args = ap.parse_args()

    authors = ([a.strip() for a in args.todo_authors.split(",")]
               if args.todo_authors else None)
    jargon = ([j.strip() for j in args.domain_jargon.split(",")]
              if args.domain_jargon else None)

    # Load
    sections = load_sections(args.file,
                             todo_authors=authors,
                             min_words=args.min_words)
    if not sections:
        print("No sections found (all below --min-words threshold?).",
              file=sys.stderr)
        sys.exit(1)

    # Score
    for sec in sections:
        score_section(sec, domain_jargon=jargon)

    # Cross-section analysis
    parallelism = detect_template_parallelism(sections)

    # Sort
    sections.sort(key=lambda s: s["ai_score_normalized"], reverse=True)

    # Output
    if args.json:
        out = {
            "cross_section_warnings": parallelism,
            "sections": sections,
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print_report(sections, parallelism, top_n=args.top)


if __name__ == "__main__":
    main()
