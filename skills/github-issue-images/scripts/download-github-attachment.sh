#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  download-github-attachment.sh --url <attachment_url> --output <output_path>

Notes:
  - Intended for GitHub issue / PR attachment URLs such as:
    https://github.com/user-attachments/assets/<id>
  - Requires `gh` to be installed and authenticated.
EOF
}

url=""
output=""

while (($# > 0)); do
  case "$1" in
    --url)
      url="${2:-}"
      shift 2
      ;;
    --output)
      output="${2:-}"
      shift 2
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

if [[ -z "$url" || -z "$output" ]]; then
  usage >&2
  exit 2
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "gh is required but not found on PATH" >&2
  exit 2
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required but not found on PATH" >&2
  exit 2
fi

token="$(gh auth token 2>/dev/null || true)"
if [[ -z "$token" ]]; then
  echo "Failed to read GitHub auth token. Run 'gh auth status' first." >&2
  exit 2
fi

mkdir -p "$(dirname "$output")"

headers_file="$(mktemp)"
trap 'rm -f "$headers_file"' EXIT

curl -fsSL \
  -D "$headers_file" \
  -H "Authorization: Bearer $token" \
  -L "$url" \
  -o "$output"

content_type="$(
  awk 'tolower($1) == "content-type:" {print tolower($2)}' "$headers_file" | \
    tail -n 1 | tr -d '\r'
)"

bytes="$(wc -c < "$output" | tr -d '[:space:]')"

echo "saved: $output"
if [[ -n "$content_type" ]]; then
  echo "content-type: $content_type"
fi
echo "bytes: $bytes"
