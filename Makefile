# Mirrors ~/projects/dotfiles/Makefile's target vocabulary (help / test /
# test-lint / advisory / docs-report / worktree include) so both repos answer to
# the same muscle memory. The bodies differ — this repo's suite is pytest over
# .claude/hooks/*.py, not bats.

.PHONY: help test test-lint test-pytest test-paths advisory docs-report install-hooks

help:
	@echo "make test          - run the full verification suite (lint + pytest + PII gate)"
	@echo "make test-lint     - shellcheck own shell scripts + ruff the Python"
	@echo "make test-pytest   - run the pytest suite (tests/)"
	@echo "make test-paths    - blocking identity/PII scan (same gate as hooks/pre-commit)"
	@echo "make advisory      - alias for test-paths, kept for dotfiles parity"
	@echo "make docs-report   - advisory size report for instruction files (never blocks)"
	@echo "make install-hooks - activate the repo's git secret-gate hooks (./install.sh)"
	@echo "make syncwt|commit|commitwt - shared worktree targets (~/.config/make/worktree.mk)"

test: test-lint test-pytest test-paths

# Vendored skills under .claude/skills/ are upstream imports — their scripts are
# excluded from both linters so third-party style never gates this repo.
test-lint:
	@echo "[1/3] shellcheck + ruff"
	@if ! command -v shellcheck >/dev/null 2>&1; then \
		echo "error: shellcheck not installed (apt install shellcheck)" >&2; \
		exit 1; \
	fi
	@git ls-files -z '*.sh' 'hooks/*' ':!:.claude/skills/**' | xargs -0r shellcheck -x
	@echo "shellcheck: ok"
	@if ! command -v ruff >/dev/null 2>&1; then \
		echo "error: ruff not installed (pip install ruff)" >&2; \
		exit 1; \
	fi
	@ruff check .claude/hooks scripts tests

test-pytest:
	@echo "[2/3] pytest"
	@python3 -m pytest -q

# Blocking here, unlike dotfiles' non-blocking `advisory`: this repo is public
# and check-hardcoded-paths.sh is the PII gate hooks/pre-commit enforces, so
# `make test` fails on a hit rather than printing one.
test-paths:
	@echo "[3/3] identity/PII check"
	@./scripts/check-hardcoded-paths.sh

advisory: test-paths

# Deliberately NOT a dependency of `test` — a look-at-it-when-you-want report,
# not a gate. Always exits 0.
docs-report:
	@./scripts/docs-report.sh

install-hooks:
	@./install.sh

# Shared worktree/commit targets (syncwt, commit, commitwt). At the bottom so the
# include can't steal the default goal (first target read wins -> keep `help`).
-include $(HOME)/.config/make/worktree.mk
