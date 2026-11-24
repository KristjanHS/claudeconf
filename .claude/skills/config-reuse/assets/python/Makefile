# A stale uv.lock fails every uv command instead of being silently rewritten mid-gate.
export UV_LOCKED := 1
# Empty tree: diff --check against it covers every tracked file, committed or not.
EMPTY_TREE := 4b825dc642cb6eb9a060e54bf8d69288fbee4904

.PHONY: help sync check lint fmt test audit push-gate setup-hooks pre-commit

help:
	@echo "make sync     - uv sync (locked, all groups) + uv pip check"
	@echo "make check    - verification gate (syncwt runs it): whitespace + lint + test"
	@echo "make lint     - ruff check + ruff format --check + pyright"
	@echo "make fmt      - ruff check --fix + ruff format (rewrites files)"
	@echo "make test     - pytest (skips while tests/ is absent)"
	@echo "make audit    - uv audit: known vulnerabilities in uv.lock"
	@echo "make setup-hooks - install pre-commit (commit) + make push-gate (push) git hooks"
	@echo "make pre-commit  - run all commit-stage hooks on all files"
	@echo "make push-gate   - pre-push: clean tree + pushed ref == HEAD, then check"
	@echo "make syncwt|commit|commitwt - shared worktree targets (~/.config/make/worktree.mk)"

sync:
	uv sync --locked --all-groups
	uv pip check

check:
	@git diff --check $(EMPTY_TREE) -- . ':!*.md'
	@$(MAKE) --no-print-directory lint test

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run pyright

fmt:
	uv run ruff check --fix .
	uv run ruff format .

test:
	@if [ -d tests ]; then uv run pytest -q || [ $$? -eq 5 ]; else echo "pytest: no tests/ yet"; fi

audit:
	uv audit

# Pre-push gate. `check` reads the working tree, so require it to BE the pushed commit:
# clean (untracked included) and the pushed ref == HEAD (PRE_COMMIT_TO_REF set by pre-commit).
push-gate:
	@test -z "$$(git status --porcelain)" || { echo "push-gate: commit or stash first — check gates the working tree" >&2; exit 1; }
	@test -z "$${PRE_COMMIT_TO_REF:-}" || test "$$(git rev-parse "$$PRE_COMMIT_TO_REF")" = "$$(git rev-parse HEAD)" \
	  || { echo "push-gate: push the checked-out branch, or check it out first" >&2; exit 1; }
	@$(MAKE) --no-print-directory check

setup-hooks:
	uv run pre-commit install

pre-commit:
	uv run pre-commit run --all-files

# Bottom, so the include can't steal the default goal; `-include` so clones without dotfiles still work.
-include $(HOME)/.config/make/worktree.mk
