"""Shared marker-block helpers: swap generated text between a start/end marker pair.

Callers own the markers and map `MarkerError` to their own exit code.
"""

from __future__ import annotations


class MarkerError(ValueError):
    """Marker pair missing, duplicated, or out of order."""


def has_markers(text: str, markers: tuple[str, str]) -> bool:
    """True when either marker appears; a half pair is then caught by replace_between."""
    return any(m in text for m in markers)


def replace_between(text: str, start: str, end: str, body: str) -> str:
    """Swap the bytes between exactly one `start` and one later `end`; all else untouched."""
    if text.count(start) != 1 or text.count(end) != 1:
        raise MarkerError(f"need exactly one {start} and one {end}")
    i, j = text.index(start) + len(start), text.index(end)
    if j < i:
        raise MarkerError(f"{end} comes before {start}")
    return text[:i] + "\n" + body + text[j:]
