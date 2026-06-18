"""Shared fixtures for the hook test suite.

The hooks live in `.claude/hooks/` with hyphenated filenames, so they are not
importable as normal modules. `hook_module` loads one by path via importlib;
`hook_path` exposes the path for subprocess-style (stdin payload) tests.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"


def load_hook(filename: str):
    """Load a hyphen-named hook script as a module object."""
    path = HOOKS_DIR / filename
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def budget_hook_path() -> Path:
    return HOOKS_DIR / "impag-budget-check.py"


@pytest.fixture(scope="session")
def budget_hook():
    return load_hook("impag-budget-check.py")
