"""docs_quality — shared rule definitions for docs slop + lexical density.

Single source of truth for:
  S2 slop wordlist + phrase list (used by docs-bloat-gate hook for
    advisory net-added detection — warns, never blocks — and by the
    condense skill as advisory pre-checks before applying user-approved Edits).
  S3 lexical-density threshold + tokenizer (same dual-consumer split).

Hook concerns NOT here: payload handling.
"""

from __future__ import annotations

import re
from collections import Counter

# --- S2: AI-slop stoplist ------------------------------------------------
SLOP_WORDS = {
    # transition adverbs
    "furthermore",
    "moreover",
    "additionally",
    "consequently",
    "subsequently",
    "accordingly",
    "nevertheless",
    "notwithstanding",
    # hedge adverbs
    "fundamentally",
    "essentially",
    "ultimately",
    # AI tells (single-word)
    "comprehensive",
    "robust",
    "seamless",
    "leverage",
    "utilize",
}
SLOP_PHRASES = (
    # hedges (multi-word)
    "it's worth noting",
    "it should be noted",
    "it is important to",
    "that said",
    "having said that",
    "in essence",
    "at its core",
    "while this may vary",
    "in the context of",
    # AI tells (multi-word)
    "delve into",
    "navigate the",
    "landscape of",
    "realm of",
    "tapestry of",
)

# ~150 English function words for S3 lexical-density stoplist.
FUNCTION_WORDS = {
    # articles
    "a",
    "an",
    "the",
    # pronouns
    "i",
    "me",
    "my",
    "mine",
    "we",
    "us",
    "our",
    "ours",
    "you",
    "your",
    "yours",
    "he",
    "him",
    "his",
    "she",
    "her",
    "hers",
    "it",
    "its",
    "they",
    "them",
    "their",
    "theirs",
    "this",
    "that",
    "these",
    "those",
    "who",
    "whom",
    "whose",
    "which",
    "what",
    # conjunctions / subordinators
    "and",
    "or",
    "but",
    "nor",
    "so",
    "yet",
    "for",
    "if",
    "then",
    "than",
    "while",
    "although",
    "though",
    "because",
    "since",
    "unless",
    "until",
    "when",
    "where",
    "whether",
    "how",
    "why",
    "as",
    # prepositions
    "in",
    "on",
    "at",
    "to",
    "of",
    "by",
    "with",
    "from",
    "into",
    "onto",
    "upon",
    "about",
    "above",
    "across",
    "after",
    "against",
    "along",
    "among",
    "around",
    "before",
    "behind",
    "below",
    "beneath",
    "beside",
    "between",
    "beyond",
    "during",
    "except",
    "inside",
    "near",
    "outside",
    "over",
    "through",
    "throughout",
    "toward",
    "towards",
    "under",
    "underneath",
    "up",
    "down",
    "off",
    "out",
    # auxiliaries / be / have / do / modals
    "be",
    "am",
    "is",
    "are",
    "was",
    "were",
    "been",
    "being",
    "have",
    "has",
    "had",
    "having",
    "do",
    "does",
    "did",
    "doing",
    "will",
    "would",
    "shall",
    "should",
    "can",
    "could",
    "may",
    "might",
    "must",
    "ought",
    # determiners / quantifiers
    "no",
    "not",
    "all",
    "any",
    "some",
    "none",
    "both",
    "each",
    "every",
    "much",
    "many",
    "more",
    "most",
    "less",
    "least",
    "few",
    "several",
    "such",
    "same",
    "other",
    "another",
    "own",
    # discourse / fillers
    "only",
    "just",
    "very",
    "too",
    "also",
    "even",
    "again",
    "here",
    "there",
    "now",
    "well",
    "like",
    "yes",
    "ok",
    # contraction stubs (after \w+ tokenization)
    "s",
    "t",
    "re",
    "ve",
    "ll",
    "d",
    "m",
}

DENSITY_THRESHOLD = 0.45


_SLOP_WORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in sorted(SLOP_WORDS)) + r")\b",
    re.IGNORECASE,
)


def slop_hit_counts(text: str) -> Counter[str]:
    """Return a Counter of slop-pattern occurrences in ``text``.

    Counts (not just presence) so net-added detection can catch the
    "added one more occurrence" case — set-difference would miss the
    second instance when the first already appears in prior text.
    """
    counts: Counter[str] = Counter()
    if not text:
        return counts
    for m in _SLOP_WORD_RE.finditer(text):
        counts[m.group(1).lower()] += 1
    lower = text.lower()
    for ph in SLOP_PHRASES:
        n, start = 0, 0
        while (idx := lower.find(ph, start)) != -1:
            n += 1
            start = idx + len(ph)
        if n:
            counts[ph] += n
    return counts


def find_slop(text: str) -> list[str]:
    """Return slop terms present in ``text``. Empty list = clean."""
    return sorted(slop_hit_counts(text).keys())


def lexical_density(text: str) -> float:
    """Content-word ratio. Returns 0.0–1.0; 1.0 if ``text`` has no tokens."""
    tokens = re.findall(r"\w+", text.lower())
    if not tokens:
        return 1.0
    content = sum(1 for t in tokens if t not in FUNCTION_WORDS)
    return content / len(tokens)


def density_threshold() -> float:
    """The shared S3 cutoff (0.45 today)."""
    return DENSITY_THRESHOLD
