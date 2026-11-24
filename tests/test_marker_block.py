"""scripts/marker_block.py: the shared marker-block helpers."""

from __future__ import annotations

import importlib.util
import sys

import pytest

from conftest import REPO_ROOT

_spec = importlib.util.spec_from_file_location(
    "marker_block", REPO_ROOT / "scripts" / "marker_block.py"
)
assert _spec is not None and _spec.loader is not None
mb = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("marker_block", mb)
_spec.loader.exec_module(mb)

START, END = "<!-- x:start -->", "<!-- x:end -->"


def test_replace_between_idempotent_and_preserves_outside():
    text = f"head\n{START}\nold\n{END}\ntail  \n"
    once = mb.replace_between(text, START, END, "new\n")
    assert once == f"head\n{START}\nnew\n{END}\ntail  \n"
    assert mb.replace_between(once, START, END, "new\n") == once


@pytest.mark.parametrize(
    ("text", "msg"),
    [
        (f"{START}\nx\n", "need exactly one"),  # end missing
        (f"x\n{END}\n", "need exactly one"),  # start missing
        (f"{START}\n{START}\n{END}\n", "need exactly one"),  # duplicate start
        (f"{START}\nx\n{END}\n{END}\n", "need exactly one"),  # duplicate end
        (f"{END}\nx\n{START}\n", "comes before"),  # reversed
    ],
    ids=["end-missing", "start-missing", "dup-start", "dup-end", "reversed"],
)
def test_replace_between_bad_markers(text, msg):
    with pytest.raises(mb.MarkerError, match=msg):
        mb.replace_between(text, START, END, "b\n")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("plain\n", False),
        (f"a {START} b\n", True),
        (f"a {END} b\n", True),
        (f"{START}\n{END}\n", True),
    ],
)
def test_has_markers(text, expected):
    assert mb.has_markers(text, (START, END)) is expected
