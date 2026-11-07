#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage:
  upload-issue-images.sh --issue <N> [--repo-dir <path>] [--remote origin]
                         [--branch issue-assets] <file>...

Notes:
  - Commits to a shared orphan branch using git plumbing only. The working
    tree, current branch, and index are left alone.
  - Prints one commit-pinned markdown image line per file to stdout.
  - ISSUE_ASSETS_BASE_URL overrides the https://github.com/<owner>/<repo> prefix.
EOF
}

die() {
  echo "upload-issue-images: $*" >&2
  exit 1
}

need_value() {
  (($# >= 2)) || die "$1 needs a value"
}

# Percent-encodes byte by byte, so multibyte names work in any locale.
urlencode() {
  local byte out=""
  for byte in $(printf '%s' "$1" | od -An -v -tx1); do
    case "$byte" in
      2d|2e|5f|7e|3[0-9]|4[1-9a-f]|5[0-9a]|6[1-9a-f]|7[0-9a])
        out+="$(printf '%b' "\\x$byte")"
        ;;
      *)
        out+="$(printf '%%%02X' "0x$byte")"
        ;;
    esac
  done
  printf '%s' "$out"
}

github_base_url() {
  local url="${1%/}"
  local re='^(https://([^/@]+@)?github\.com/|ssh://git@github\.com/|git@github\.com:)([^/]+)/([^/]+)$'
  url="${url%.git}"
  [[ "$url" =~ $re ]] || die "remote '$remote' is not on GitHub"
  echo "https://github.com/${BASH_REMATCH[3]}/${BASH_REMATCH[4]}"
}

issue=""
repo_dir="."
remote="origin"
branch="issue-assets"
files=()

while (($# > 0)); do
  case "$1" in
    --issue)
      need_value "$@"
      issue="$2"
      shift 2
      ;;
    --repo-dir)
      need_value "$@"
      repo_dir="$2"
      shift 2
      ;;
    --remote)
      need_value "$@"
      remote="$2"
      shift 2
      ;;
    --branch)
      need_value "$@"
      branch="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      usage
      die "unknown argument: $1"
      ;;
    *)
      files+=("$1")
      shift
      ;;
  esac
done

[[ "$issue" =~ ^[1-9][0-9]*$ ]] || die "--issue must be a positive integer"
((${#files[@]} > 0)) || die "at least one file is required"

names=()
for file in "${files[@]}"; do
  [[ -f "$file" ]] || die "file not found: $file"
  name="${file##*/}"
  case "$(printf '%s' "$name" | LC_ALL=C tr '[:upper:]' '[:lower:]')" in
    *.png|*.jpg|*.jpeg|*.gif|*.webp)
      ;;
    *.svg)
      echo "warning: GitHub may not render SVG from blob URLs, prefer PNG: $file" >&2
      ;;
    *)
      die "not an image (png, jpg, jpeg, gif, webp, svg): $file"
      ;;
  esac
  # Two inputs on one path would silently lose the first image.
  for seen in ${names[@]+"${names[@]}"}; do
    [[ "$seen" != "$name" ]] || die "duplicate file name: $name"
  done
  names+=("$name")
done

if [[ -n "${ISSUE_ASSETS_BASE_URL:-}" ]]; then
  base_url="${ISSUE_ASSETS_BASE_URL%/}"
else
  remote_url="$(git -C "$repo_dir" remote get-url "$remote")"
  base_url="$(github_base_url "$remote_url")" || exit 1
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
index="$tmpdir/index"

idx() {
  GIT_INDEX_FILE="$index" git -C "$repo_dir" "$@"
}

for attempt in 1 2; do
  parent=""
  ls_status=0
  git -C "$repo_dir" ls-remote --exit-code --heads "$remote" "refs/heads/$branch" \
    >/dev/null || ls_status=$?
  case "$ls_status" in
    0)
      git -C "$repo_dir" fetch --quiet --no-tags "$remote" "refs/heads/$branch" >&2
      parent="$(git -C "$repo_dir" rev-parse --verify 'FETCH_HEAD^{commit}')"
      ;;
    2)
      echo "branch $branch not found on $remote, creating it as an orphan" >&2
      ;;
    *)
      die "could not read $branch from $remote (git exit $ls_status)"
      ;;
  esac

  rm -f "$index"
  if [[ -n "$parent" ]]; then
    idx read-tree "$parent"
  fi
  for i in "${!files[@]}"; do
    blob="$(git -C "$repo_dir" hash-object -w --stdin <"${files[$i]}")"
    idx update-index --add --cacheinfo "100644,$blob,issue-$issue/${names[$i]}"
  done
  tree="$(idx write-tree)"

  if [[ -n "$parent" && "$tree" == "$(git -C "$repo_dir" rev-parse "$parent^{tree}")" ]]; then
    echo "no changes, using current tip of $branch" >&2
    commit="$parent"
    break
  fi

  message="Add images for issue #$issue"
  if [[ -n "$parent" ]]; then
    commit="$(git -C "$repo_dir" commit-tree "$tree" -p "$parent" -m "$message")"
  else
    commit="$(git -C "$repo_dir" commit-tree "$tree" -m "$message")"
  fi

  if git -C "$repo_dir" push --porcelain "$remote" "$commit:refs/heads/$branch" \
    >"$tmpdir/push"; then
    cat "$tmpdir/push" >&2
    break
  fi
  cat "$tmpdir/push" >&2

  # Matches a stale push ([rejected]) and a lost ref update ([remote rejected]).
  if ((attempt == 2)) || ! grep -q 'rejected\]' "$tmpdir/push"; then
    die "push to $remote failed"
  fi
  echo "push rejected, retrying once" >&2
done

for name in "${names[@]}"; do
  printf '![%s](%s/blob/%s/issue-%s/%s?raw=true)\n' \
    "$name" "$base_url" "$commit" "$issue" "$(urlencode "$name")"
done
