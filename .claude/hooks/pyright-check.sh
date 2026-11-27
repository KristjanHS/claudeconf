#!/bin/bash
f=$(jq -r '.tool_input.file_path // empty' 2>/dev/null)
[[ -z "$f" || "$f" != *.py ]] && exit 0
[[ -f "$f" ]] || exit 0

dir=$(cd -- "$(dirname -- "$f")" 2>/dev/null && pwd -P) || exit 0

# Config and venv can live below the session CWD (crash-dash: scripts/backtest/)
# or above the edited file (src/pkg/mod.py -> repo root), so search upward from
# the FILE, not from CWD. Bound the walk by the enclosing git repo. Outside a
# repo, DON'T climb: a loose script's config/venv lives in its own dir, and
# walking up would bind a stray ancestor .venv / pyrightconfig (e.g. ~/.venv)
# that has nothing to do with the file — pyright would then emit bogus
# missing-import errors into the hook's context.
top=$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null)
if [[ -n "$top" ]]; then
  # Climb nested/submodule git boundaries to the OUTERMOST repo root, so a file
  # in a submodule still sees the parent project's pyright config/venv.
  while outer=$(git -C "$(dirname -- "$top")" rev-parse --show-toplevel 2>/dev/null) \
        && [[ -n "$outer" && "$outer" != "$top" ]]; do
    top="$outer"
  done
else
  top="$dir"
fi

cfg_dir="" cfg_file="" venv_dir="" d="$dir"
while :; do
  if [[ -z "$cfg_dir" ]]; then
    for c in "$d/pyrightconfig.json" "$d/pyrightconfig.jsonc"; do
      [[ -f "$c" ]] && { cfg_dir="$d"; cfg_file="$c"; break; }
    done
    if [[ -z "$cfg_dir" ]] && grep -qE '^\[tool\.pyright(\.|\])' "$d/pyproject.toml" 2>/dev/null; then
      cfg_dir="$d" cfg_file="$d/pyproject.toml"
    fi
  fi
  if [[ -z "$venv_dir" ]]; then
    for v in "$d/.venv" "$d/venv"; do
      [[ -x "$v/bin/python" ]] && { venv_dir="$v"; break; }
    done
  fi
  [[ -n "$cfg_dir" && -n "$venv_dir" ]] && break
  [[ "$d" == "$top" || "$d" == "/" ]] && break
  d=$(dirname -- "$d")
done

# Prefer the project's own pyright binary (no download); fall back to PATH.
bin="pyright"
[[ -n "$venv_dir" && -x "$venv_dir/bin/pyright" ]] && bin="$venv_dir/bin/pyright"

args=(--level error)

# A project config wins outright: it carries pythonVersion, strict globs, and
# often its own venvPath. Pass the config FILE, not its dir: `--project <dir>`
# only auto-finds pyrightconfig.json, so a .jsonc (or pyproject.toml) would be
# silently ignored and pyright would fall back to defaults.
# With NO config, pass no --project at all. Pyright roots local-import search
# at the config file's directory, so the old fallback to
# ~/.claude/pyright/pyrightconfig.json teleported the root there and every
# sibling import falsely errored as reportMissingImports. Standard-mode
# defaults match what the global config set — under --level error dropping it
# changes nothing else.
if [[ -n "$cfg_file" ]]; then
  args+=(--project "$cfg_file")
fi

# --pythonpath overrides the config's interpreter resolution, so only supply it
# when the config isn't already choosing an interpreter itself (it may name a
# venv other than the .venv/ we happened to find). A config can pin the
# interpreter via any of venvPath/pythonPath/defaultInterpreterPath (JSON `key:`
# or TOML `key =`), so match the key form — not a bare substring, which a
# comment or unrelated glob would trip.
if [[ -n "$venv_dir" ]] \
   && ! grep -qE '"?(venvPath|pythonPath|defaultInterpreterPath)"?[[:space:]]*[:=]' "${cfg_file:-/dev/null}" 2>/dev/null; then
  args+=(--pythonpath "$venv_dir/bin/python")
fi

# Run from $top: configless pyright roots at its CWD (verified 1.1.409), and
# the hook's inherited CWD is the session dir — a file outside it (scratchpad
# scripts) would get a root it doesn't live under and its sibling imports
# would falsely error. With a config the root is the config's dir and CWD is
# ignored, so this is a no-op there. Strip the pyright-python wrapper's
# version-update nag from hook context.
output=$(cd -- "$top" 2>/dev/null && "$bin" "${args[@]}" "$f" 2>&1 \
  | grep -vE 'new pyright version available|PYRIGHT_PYTHON_FORCE_VERSION')
if [ -n "$output" ]; then
  jq -n --arg ctx "$output" '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:$ctx}}'
fi
exit 0
