#!/usr/bin/env bash
set -euo pipefail

# Sync markdown prompts to Codex and Claude destinations via symlinks.
#
# Symlinks (not copies) so that edits under prompts/ are reflected immediately
# in both destinations without re-running this script. Re-run only to pick up
# newly added prompts or to prune ones deleted from the repo.
# Only symlinked destinations self-heal during prune; old regular-file copies
# are left untouched because this script cannot prove ownership.
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROMPTS_DIR="$SCRIPT_DIR/prompts"
CODEX_DEST="$HOME/.codex/prompts"
CLAUDE_DEST="$HOME/.claude/commands"

if [[ ! -d "$PROMPTS_DIR" ]]; then
  echo "prompts directory not found: $PROMPTS_DIR" >&2
  exit 1
fi

link_file() {
  local src="$1"
  local target="$2"

  mkdir -p "$(dirname "$target")"

  # Already the correct symlink -> nothing to do.
  if [[ -L "$target" && "$(readlink "$target")" == "$src" ]]; then
    return
  fi

  if [[ -e "$target" && ! -L "$target" ]]; then
    printf 'warn: refusing to replace existing non-symlink %s\n' "$target" >&2
    return
  fi

  # Replace a wrong or stale symlink with a fresh symlink.
  ln -sfn "$src" "$target"
  echo "Linked: $target -> $src"
}

# 1. Create/refresh a symlink for every source prompt.
#    Codex flattens nested paths (task/foo.md -> task_foo.md); Claude keeps them nested.
while IFS= read -r -d '' file; do
  rel="${file#"$PROMPTS_DIR"/}"
  link_file "$file" "$CLAUDE_DEST/$rel"
  link_file "$file" "$CODEX_DEST/${rel//\//_}"
done < <(find "$PROMPTS_DIR" -type f -name '*.md' -print0)

# 2. Prune symlinks that point back into this prompts dir but whose source is
#    gone (i.e. prompts deleted from the repo). Only touches our own dangling
#    links, never unrelated command files.
prune_dangling() {
  local dest="$1"
  [[ -d "$dest" ]] || return 0
  while IFS= read -r -d '' link; do
    local tgt
    tgt="$(readlink "$link" 2>/dev/null)" || continue
    if [[ "$tgt" == "$PROMPTS_DIR"/* && ! -e "$link" ]]; then
      rm -v "$link" || printf 'warn: could not remove %s\n' "$link" >&2
    fi
  done < <(find "$dest" -type l -print0)
}
prune_dangling "$CLAUDE_DEST"
prune_dangling "$CODEX_DEST"
