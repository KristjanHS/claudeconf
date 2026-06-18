#!/usr/bin/env bash
# Usage: install.sh <owner/repo> [skill_subpath]
# Installs a skill from GitHub into ~/.claude/skills/

set -euo pipefail

TARGET_DIR="$HOME/.claude/skills"
INPUT="${1:-}"
SUBPATH="${2:-}"

if [[ -z "$INPUT" ]]; then
  echo "ERROR: No repo specified." >&2
  echo "Usage: install.sh owner/repo [path/to/skill]" >&2
  exit 1
fi

# Strip GitHub URL boilerplate if user passed full URL
# e.g. https://github.com/owner/repo/tree/branch/path -> owner/repo + path
if [[ "$INPUT" =~ ^https?://github\.com/([^/]+/[^/]+)/tree/[^/]+(/.*)?$ ]]; then
  REPO="${BASH_REMATCH[1]}"
  URL_SUBPATH="${BASH_REMATCH[2]#/}"  # strip leading slash
  # If user also passed SUBPATH explicitly, prefer that; otherwise use URL_SUBPATH
  SUBPATH="${SUBPATH:-$URL_SUBPATH}"
else
  REPO="$INPUT"
fi

CLONE_DIR="$(mktemp -d)"
trap 'rm -rf "$CLONE_DIR"' EXIT

echo "Cloning $REPO (shallow)..."
git clone --depth=1 "https://github.com/$REPO.git" "$CLONE_DIR" 2>&1

if [[ -n "$SUBPATH" ]]; then
  SKILL_SRC="$CLONE_DIR/$SUBPATH"
else
  SKILL_SRC="$CLONE_DIR"
fi

if [[ ! -d "$SKILL_SRC" ]]; then
  echo "ERROR: Path '$SUBPATH' not found in repo $REPO" >&2
  exit 1
fi

# Check if this folder directly contains SKILL.md
if [[ -f "$SKILL_SRC/SKILL.md" ]]; then
  # Use subpath basename if given, otherwise fall back to repo name
  SKILL_NAME="${SUBPATH:+$(basename "$SKILL_SRC")}${SUBPATH:-$(basename "$REPO")}"
  DEST="$TARGET_DIR/$SKILL_NAME"
  if [[ -d "$DEST" ]]; then
    echo "WARNING: $DEST already exists — overwriting."
    rm -rf "$DEST"
  fi
  mkdir -p "$TARGET_DIR"
  cp -r "$SKILL_SRC" "$DEST"
  echo "✓ Installed '$SKILL_NAME' to $DEST"
else
  # Look for skill subdirectories (each containing SKILL.md)
  FOUND=()
  while IFS= read -r -d '' dir; do
    FOUND+=("$dir")
  done < <(find "$SKILL_SRC" -maxdepth 2 -name "SKILL.md" -printf '%h\0')

  if [[ ${#FOUND[@]} -eq 0 ]]; then
    echo "ERROR: No SKILL.md found in '$SUBPATH' or its subdirectories." >&2
    exit 1
  fi

  echo "Found ${#FOUND[@]} skill(s):"
  for dir in "${FOUND[@]}"; do
    SKILL_NAME="$(basename "$dir")"
    DEST="$TARGET_DIR/$SKILL_NAME"
    if [[ -d "$DEST" ]]; then
      echo "  WARNING: $DEST already exists — overwriting."
      rm -rf "$DEST"
    fi
    mkdir -p "$TARGET_DIR"
    cp -r "$dir" "$DEST"
    echo "  ✓ Installed '$SKILL_NAME' to $DEST"
  done
fi
