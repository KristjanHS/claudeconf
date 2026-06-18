#!/usr/bin/env bash
# claudeconf — one optional setup step: activate the git secret-gate hooks.
#
# This points git at the repo's hooks/ directory (pre-commit + pre-push) for
# THIS clone only. It does not touch your ~/.claude config or any global git
# settings. Run it once after cloning if you want the secret gate locally; the
# CI gitleaks workflow runs regardless.
#
# Supply-chain note: core.hooksPath -> hooks/ means the in-repo hook scripts
# execute on every commit/push in this clone. Only run install.sh on a repo
# whose hooks/ and scripts/ you have reviewed — treat them like any code you run.
set -Eeuo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$repo_root"

chmod +x hooks/pre-commit hooks/pre-push scripts/check-hardcoded-paths.sh
git config core.hooksPath hooks

echo "ok: git hooks activated (core.hooksPath -> hooks/)"
echo "  pre-commit: gitleaks --staged + blocking identity/PII check"
echo "  pre-push:   full working-tree gitleaks scan"
if ! command -v gitleaks >/dev/null 2>&1; then
    echo "note: gitleaks is not installed — the hooks will warn and skip the"
    echo "      credential scan until you install it:"
    echo "      https://github.com/gitleaks/gitleaks#installing"
fi
