#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  link-manifest.sh --target <target_root> [--source <source_root>] [--manifest <manifest>] [--mode link|copy|check] [--force]

Defaults:
  --manifest <target_root>/docs/env-paths.txt
  --mode link

Notes:
  - The manifest must contain repo-relative file paths.
  - Blank lines and lines starting with # are ignored.
  - --source is required for link/copy mode.
  - In check mode, --source is optional.
EOF
}

mode="link"
force=0
source_root=""
target_root=""
manifest=""

while (($# > 0)); do
  case "$1" in
    --source)
      source_root="${2:-}"
      shift 2
      ;;
    --target)
      target_root="${2:-}"
      shift 2
      ;;
    --manifest)
      manifest="${2:-}"
      shift 2
      ;;
    --mode)
      mode="${2:-}"
      shift 2
      ;;
    --force)
      force=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$target_root" ]]; then
  echo "--target is required" >&2
  usage >&2
  exit 2
fi

case "$mode" in
  link|copy|check) ;;
  *)
    echo "Unsupported mode: $mode" >&2
    exit 2
    ;;
esac

target_root="$(cd "$target_root" && pwd)"

if [[ -z "$manifest" ]]; then
  manifest="$target_root/docs/env-paths.txt"
fi
manifest="$(cd "$(dirname "$manifest")" && pwd)/$(basename "$manifest")"

if [[ ! -f "$manifest" ]]; then
  echo "Manifest not found: $manifest" >&2
  exit 2
fi

if [[ "$mode" != "check" ]]; then
  if [[ -z "$source_root" ]]; then
    echo "--source is required for $mode mode" >&2
    exit 2
  fi
  source_root="$(cd "$source_root" && pwd)"
fi

failures=0

prepare_destination() {
  local dst="$1"

  mkdir -p "$(dirname "$dst")"

  if [[ -L "$dst" ]]; then
    return 0
  fi

  if [[ ! -e "$dst" ]]; then
    return 0
  fi

  if [[ "$force" -ne 1 ]]; then
    echo "Destination exists, use --force: $dst" >&2
    return 1
  fi

  if [[ -d "$dst" ]]; then
    echo "Refusing to replace directory: $dst" >&2
    return 1
  fi

  rm -f "$dst"
}

while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
  line="${raw_line%$'\r'}"

  if [[ -z "$line" || "$line" == \#* ]]; then
    continue
  fi

  if [[ "$line" = /* ]]; then
    echo "Manifest path must be relative: $line" >&2
    failures=1
    continue
  fi

  rel="$line"
  dst="$target_root/$rel"

  case "$mode" in
    check)
      if [[ -e "$dst" || -L "$dst" ]]; then
        echo "ok      $rel"
      else
        echo "missing $rel" >&2
        failures=1
      fi
      ;;
    link|copy)
      src="$source_root/$rel"

      if [[ ! -e "$src" ]]; then
        echo "Missing source: $src" >&2
        failures=1
        continue
      fi

      if ! prepare_destination "$dst"; then
        failures=1
        continue
      fi

      case "$mode" in
        link)
          ln -sfn "$src" "$dst"
          echo "linked  $rel"
          ;;
        copy)
          cp "$src" "$dst"
          echo "copied  $rel"
          ;;
      esac
      ;;
  esac
done < "$manifest"

exit "$failures"
