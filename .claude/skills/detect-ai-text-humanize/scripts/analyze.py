#!/usr/bin/env python3
"""
Statistical text analysis for AI detection.
Computes burstiness, lexical diversity, sentence variance, and other
quantitative features that help distinguish AI from human writing.

Usage:
    python analyze.py "path/to/text/file.txt"
    python analyze.py --text "Inline text to analyze..."
    echo "text" | python analyze.py --stdin
"""

import re
import sys
import json
import math
from collections import Counter
from typing import NamedTuple


class TextStats(NamedTuple):
    word_count: int
    sentence_count: int
    paragraph_count: int
    avg_sentence_length: float
    sentence_length_std: float
    burstiness_score: float  # higher = more human-like
    type_token_ratio: float
    hapax_legomena_pct: float
    em_dash_per_1000: float
    hedge_density: float  # per 100 words
    avg_paragraph_length: float  # in sentences
    paragraph_length_std: float


# Sentence boundary regex (handles abbreviations reasonably)
SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z"\'])')

# Common hedge phrases (Claude-characteristic)
HEDGE_PHRASES = [
    r"\bit'?s worth noting\b",
    r"\bthat said\b",
    r"\bthat being said\b",
    r"\bto be fair\b",
    r"\bit'?s important to\b",
    r"\btends? to\b",
    r"\bgenerally\b",
    r"\btypically\b",
    r"\bin many cases\b",
    r"\barguably\b",
    r"\bbroadly speaking\b",
    r"\bat least in part\b",
    r"\bin principle\b",
    r"\bmore or less\b",
    r"\bcould potentially\b",
    r"\bmight suggest\b",
    r"\bperhaps\b",
    r"\bit seems\b",
    r"\bappears to\b",
]

# Words Claude is instructed to avoid (absence = signal)
CLAUDE_AVOIDED_WORDS = ["genuinely", "honestly", "straightforward"]

# Common AI vocabulary markers
AI_VOCABULARY = [
    "delve", "tapestry", "multifaceted", "holistic", "robust",
    "encompasses", "fostering", "underscoring", "highlighting",
    "navigating", "landscape", "leverage", "comprehensive",
    "pivotal", "crucial", "nuanced", "salient", "noteworthy",
]


def split_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    sentences = SENTENCE_SPLIT.split(text.strip())
    # Filter out very short fragments (less than 3 words)
    return [s.strip() for s in sentences if len(s.split()) >= 3]


def split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs."""
    paragraphs = re.split(r'\n\s*\n', text.strip())
    return [p.strip() for p in paragraphs if p.strip()]


def tokenize(text: str) -> list[str]:
    """Simple word tokenization."""
    return re.findall(r'\b[a-zA-Z]+(?:\'[a-zA-Z]+)?\b', text.lower())


def compute_stats(text: str) -> TextStats:
    """Compute all statistical features for a text."""
    words = tokenize(text)
    sentences = split_sentences(text)
    paragraphs = split_paragraphs(text)

    word_count = len(words)
    sentence_count = len(sentences)
    paragraph_count = len(paragraphs)

    if word_count == 0 or sentence_count == 0:
        return TextStats(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

    # Sentence lengths
    sent_lengths = [len(s.split()) for s in sentences]
    avg_sent_len = sum(sent_lengths) / len(sent_lengths)
    sent_len_std = math.sqrt(
        sum((l - avg_sent_len) ** 2 for l in sent_lengths) / len(sent_lengths)
    )

    # Burstiness (normalized sentence length variance)
    # Higher = more human-like variation
    burstiness = sent_len_std / avg_sent_len if avg_sent_len > 0 else 0

    # Lexical diversity (TTR)
    word_freq = Counter(words)
    unique_words = len(word_freq)
    ttr = unique_words / word_count if word_count > 0 else 0

    # Hapax legomena (words appearing exactly once)
    hapax = sum(1 for count in word_freq.values() if count == 1)
    hapax_pct = hapax / unique_words * 100 if unique_words > 0 else 0

    # Em-dash frequency (per 1000 words)
    em_dash_count = text.count("—") + text.count("--")
    em_dash_per_1000 = em_dash_count / word_count * 1000 if word_count > 0 else 0

    # Hedge density (per 100 words)
    hedge_count = sum(
        len(re.findall(pattern, text, re.IGNORECASE))
        for pattern in HEDGE_PHRASES
    )
    hedge_density = hedge_count / word_count * 100 if word_count > 0 else 0

    # Paragraph statistics
    para_sent_counts = []
    for para in paragraphs:
        para_sents = split_sentences(para)
        para_sent_counts.append(max(len(para_sents), 1))

    avg_para_len = sum(para_sent_counts) / len(para_sent_counts) if para_sent_counts else 0
    para_len_std = math.sqrt(
        sum((l - avg_para_len) ** 2 for l in para_sent_counts) / len(para_sent_counts)
    ) if para_sent_counts else 0

    return TextStats(
        word_count=word_count,
        sentence_count=sentence_count,
        paragraph_count=paragraph_count,
        avg_sentence_length=round(avg_sent_len, 1),
        sentence_length_std=round(sent_len_std, 1),
        burstiness_score=round(burstiness, 3),
        type_token_ratio=round(ttr, 3),
        hapax_legomena_pct=round(hapax_pct, 1),
        em_dash_per_1000=round(em_dash_per_1000, 1),
        hedge_density=round(hedge_density, 2),
        avg_paragraph_length=round(avg_para_len, 1),
        paragraph_length_std=round(para_len_std, 1),
    )


def count_ai_vocabulary(text: str) -> dict:
    """Count AI-characteristic vocabulary."""
    text_lower = text.lower()
    found = {}
    for word in AI_VOCABULARY:
        count = len(re.findall(rf'\b{word}\b', text_lower))
        if count > 0:
            found[word] = count
    return found


def check_avoided_words(text: str) -> dict:
    """Check for presence/absence of words Claude is instructed to avoid."""
    text_lower = text.lower()
    return {
        word: len(re.findall(rf'\b{word}\b', text_lower))
        for word in CLAUDE_AVOIDED_WORDS
    }


def interpret(stats: TextStats, ai_vocab: dict, avoided: dict) -> dict:
    """Produce interpretation of statistical features."""
    signals = []
    ai_score_adjustments = 0

    # Burstiness
    if stats.burstiness_score < 0.35:
        signals.append(f"Low burstiness ({stats.burstiness_score}) — AI-typical rhythmic uniformity")
        ai_score_adjustments += 10
    elif stats.burstiness_score > 0.55:
        signals.append(f"High burstiness ({stats.burstiness_score}) — human-like variation")
        ai_score_adjustments -= 10

    # Sentence length variance
    if stats.sentence_length_std < 6:
        signals.append(f"Low sentence length variance (std={stats.sentence_length_std}) — AI-typical")
        ai_score_adjustments += 8
    elif stats.sentence_length_std > 12:
        signals.append(f"High sentence length variance (std={stats.sentence_length_std}) — human-typical")
        ai_score_adjustments -= 8

    # TTR
    if stats.type_token_ratio < 0.50 and stats.word_count > 200:
        signals.append(f"Low lexical diversity (TTR={stats.type_token_ratio}) — AI-typical")
        ai_score_adjustments += 5

    # Em-dashes
    if stats.em_dash_per_1000 > 6:
        signals.append(f"High em-dash usage ({stats.em_dash_per_1000}/1000 words) — Claude-typical")
        ai_score_adjustments += 8

    # Hedge density
    if stats.hedge_density > 2.5:
        signals.append(f"High hedge density ({stats.hedge_density}/100 words) — AI-typical")
        ai_score_adjustments += 10
    elif stats.hedge_density < 1.0:
        signals.append(f"Low hedge density ({stats.hedge_density}/100 words) — human-typical")
        ai_score_adjustments -= 5

    # Paragraph uniformity
    if stats.paragraph_length_std < 1.0 and stats.paragraph_count > 3:
        signals.append(f"Uniform paragraph lengths (std={stats.paragraph_length_std}) — AI-typical")
        ai_score_adjustments += 5

    # AI vocabulary
    if len(ai_vocab) >= 3:
        words_found = ", ".join(ai_vocab.keys())
        signals.append(f"Multiple AI-characteristic words found: {words_found}")
        ai_score_adjustments += min(len(ai_vocab) * 3, 15)

    # Avoided words
    all_avoided = all(count == 0 for count in avoided.values())
    if all_avoided and stats.word_count > 300:
        signals.append(
            "Absence of 'genuinely', 'honestly', 'straightforward' — "
            "words Claude is instructed to avoid"
        )
        ai_score_adjustments += 5

    # Base probability (start at 50%, adjust)
    base = 50
    probability = max(0, min(100, base + ai_score_adjustments))

    return {
        "statistical_ai_probability": probability,
        "signals": signals,
        "note": "Statistical analysis only. Combine with pattern/content analysis for full assessment."
    }


def analyze(text: str) -> dict:
    """Full analysis pipeline. Returns JSON-serializable dict."""
    stats = compute_stats(text)
    ai_vocab = count_ai_vocabulary(text)
    avoided = check_avoided_words(text)
    interpretation = interpret(stats, ai_vocab, avoided)

    return {
        "statistics": stats._asdict(),
        "ai_vocabulary_found": ai_vocab,
        "avoided_words_check": avoided,
        "interpretation": interpretation,
    }


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "--text":
            text = " ".join(sys.argv[2:])
        elif sys.argv[1] == "--stdin":
            text = sys.stdin.read()
        else:
            with open(sys.argv[1], "r") as f:
                text = f.read()
    else:
        text = sys.stdin.read()

    result = analyze(text)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
