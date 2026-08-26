#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  browser-quick.sh ACTION [--url URL | --html-file FILE]
                          [--data JSON | --data-file FILE]
                          [--output FILE] [--dry-run]
                          [--expect-text TEXT] [--expect-min-bytes N]
                          [--browser kitesurf|chromium]
                          [--connect-timeout SECONDS] [--max-time SECONDS]

Actions:
  content screenshot pdf markdown snapshot accessibilityTree
  scrape json links

Environment:
  CLOUDFLARE_ACCOUNT_ID (or CF_ACCOUNT_ID)
  CLOUDFLARE_API_TOKEN  (or CF_API_TOKEN)
USAGE
}

die() {
  printf 'browser-quick: %s\n' "$*" >&2
  exit 2
}

semantic_failure() {
  printf 'browser-quick: semantic validation failed: %s (exit 65)\n' "$*" >&2
  exit 65
}

[[ $# -gt 0 ]] || { usage >&2; exit 2; }
command -v jq >/dev/null 2>&1 || die "jq is required"
command -v curl >/dev/null 2>&1 || die "curl is required"

action="$1"
shift

case "$action" in
  content|screenshot|pdf|markdown|snapshot|accessibilityTree|scrape|json|links) ;;
  -h|--help) usage; exit 0 ;;
  *) die "unsupported action: $action" ;;
esac

url=""
html_file=""
data_json='{}'
data_file=""
data_supplied=false
data_file_supplied=false
output=""
dry_run=false
case "$action" in
  screenshot|pdf|snapshot) browser="chromium" ;;
  *) browser="kitesurf" ;;
esac
connect_timeout=15
max_time=120
expect_min_bytes=""
expect_texts=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --url)
      [[ $# -ge 2 ]] || die "--url requires a value"
      url="$2"
      shift 2
      ;;
    --html-file)
      [[ $# -ge 2 ]] || die "--html-file requires a value"
      html_file="$2"
      shift 2
      ;;
    --data)
      [[ $# -ge 2 ]] || die "--data requires a value"
      $data_file_supplied && die "use only one of --data and --data-file"
      data_json="$2"
      data_supplied=true
      shift 2
      ;;
    --data-file)
      [[ $# -ge 2 ]] || die "--data-file requires a value"
      $data_supplied && die "use only one of --data and --data-file"
      data_file="$2"
      data_file_supplied=true
      shift 2
      ;;
    --output)
      [[ $# -ge 2 ]] || die "--output requires a value"
      output="$2"
      shift 2
      ;;
    --dry-run)
      dry_run=true
      shift
      ;;
    --expect-text)
      [[ $# -ge 2 ]] || die "--expect-text requires a value"
      [[ -n "$2" ]] || die "--expect-text must not be empty"
      expect_texts+=("$2")
      shift 2
      ;;
    --expect-min-bytes)
      [[ $# -ge 2 ]] || die "--expect-min-bytes requires a value"
      expect_min_bytes="$2"
      shift 2
      ;;
    --browser)
      [[ $# -ge 2 ]] || die "--browser requires a value"
      browser="$2"
      shift 2
      ;;
    --connect-timeout)
      [[ $# -ge 2 ]] || die "--connect-timeout requires a value"
      connect_timeout="$2"
      shift 2
      ;;
    --max-time)
      [[ $# -ge 2 ]] || die "--max-time requires a value"
      max_time="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *) die "unknown argument: $1" ;;
  esac
done

[[ -z "$url" || -z "$html_file" ]] || die "use only one of --url and --html-file"
case "$browser" in
  kitesurf|chromium) ;;
  *) die "--browser must be kitesurf or chromium" ;;
esac
[[ "$action" != "screenshot" && "$action" != "pdf" || -n "$output" || "$dry_run" == true ]] || die "$action requires --output FILE"
jq -en --arg value "$connect_timeout" '$value | test("^[1-9][0-9]*$") and (($value | tonumber) <= 300)' >/dev/null || die "--connect-timeout must be an integer from 1 through 300"
jq -en --arg value "$max_time" '$value | test("^[1-9][0-9]*$") and (($value | tonumber) <= 3600)' >/dev/null || die "--max-time must be an integer from 1 through 3600"
if [[ -n "$expect_min_bytes" ]]; then
  jq -en --arg value "$expect_min_bytes" '
    ($value | test("^[1-9][0-9]*$")) and (($value | tonumber) <= 1073741824)
  ' >/dev/null || die "--expect-min-bytes must be a positive integer no greater than 1073741824"
  expect_min_bytes="$(jq -nr --arg value "$expect_min_bytes" '$value | tonumber | tostring')"
fi
if [[ "$action" == "screenshot" || "$action" == "pdf" ]]; then
  (( ${#expect_texts[@]} == 0 )) || die "--expect-text is not supported for binary actions"
fi
[[ -z "$html_file" || -f "$html_file" ]] || die "HTML file not found: $html_file"
[[ -z "$data_file" || -f "$data_file" ]] || die "data file not found: $data_file"
if [[ -n "$output" ]]; then
  output_dir="$(dirname "$output")"
  [[ -d "$output_dir" ]] || die "output directory not found: $output_dir"
fi

if [[ -n "$data_file" ]]; then
  data_json="$(<"$data_file")"
fi

jq -e 'type == "object"' >/dev/null <<<"$data_json" || die "request data must be a JSON object"

request_body="$data_json"
if [[ -n "$url" ]]; then
  request_body="$(jq -c --arg url "$url" '. + {url: $url}' <<<"$request_body")"
elif [[ -n "$html_file" ]]; then
  request_body="$(jq -c --rawfile html "$html_file" '. + {html: $html}' <<<"$request_body")"
fi

jq -e '
  ((has("url") and (has("html") | not) and (.url | type == "string" and length > 0)) or
   (has("html") and (has("url") | not) and (.html | type == "string" and length > 0)))
' >/dev/null <<<"$request_body" || die "request must contain exactly one non-empty url or string html"

if [[ "$action" == "scrape" ]]; then
  jq -e '
    has("elements") and (.elements | type == "array" and length > 0) and
    all(.elements[]; type == "object" and has("selector") and (.selector | type == "string" and length > 0))
  ' >/dev/null <<<"$request_body" || die "scrape requires a non-empty elements array with selector strings"
fi

if [[ "$action" == "json" ]]; then
  jq -e '
    (has("prompt") and (.prompt | type == "string" and length > 0)) or
    (has("response_format") and
     (.response_format | type == "object" and .type == "json_schema" and
      has("json_schema") and (.json_schema | type == "object" and length > 0)))
  ' >/dev/null <<<"$request_body" || die "json requires a non-empty prompt or response_format object"
fi

endpoint="https://api.cloudflare.com/client/v4/accounts"
endpoint_suffix=""
if [[ "$browser" == "kitesurf" ]]; then
  endpoint_suffix='?browser=kitesurf'
fi
account_id="${CLOUDFLARE_ACCOUNT_ID:-${CF_ACCOUNT_ID:-}}"
api_token="${CLOUDFLARE_API_TOKEN:-${CF_API_TOKEN:-}}"

if $dry_run; then
  request_keys="$(jq -c 'keys' <<<"$request_body")"
  expect_text_count="${#expect_texts[@]}"
  jq -n \
    --arg action "$action" \
    --arg endpoint "$endpoint/<ACCOUNT_ID>/browser-run/$action$endpoint_suffix" \
    --arg browser "$browser" \
    --argjson expect_text_count "$expect_text_count" \
    --arg expect_min_bytes "$expect_min_bytes" \
    --argjson request_keys "$request_keys" \
    '{
      action: $action,
      endpoint: $endpoint,
      browser: $browser,
      request_keys: $request_keys,
      semantic_checks: {
        expect_text_count: $expect_text_count,
        expect_min_bytes: (if $expect_min_bytes == "" then null else ($expect_min_bytes | tonumber) end)
      }
    }'
  exit 0
fi

[[ -n "$account_id" ]] || die "set CLOUDFLARE_ACCOUNT_ID or CF_ACCOUNT_ID"
[[ -n "$api_token" ]] || die "set CLOUDFLARE_API_TOKEN or CF_API_TOKEN"

endpoint="$endpoint/$account_id/browser-run/$action$endpoint_suffix"

request_file=""
header_file=""
response_file=""
cleanup() {
  local status=$?
  local cleanup_status=0
  trap - EXIT INT TERM
  [[ -z "$request_file" ]] || rm -f "$request_file" || cleanup_status=$?
  [[ -z "$header_file" ]] || rm -f "$header_file" || cleanup_status=$?
  [[ -z "$response_file" ]] || rm -f "$response_file" || cleanup_status=$?
  if (( status != 0 )); then
    exit "$status"
  fi
  exit "$cleanup_status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

request_file="$(mktemp "${TMPDIR:-/tmp}/browser-quick-request.XXXXXX")"
header_file="$(mktemp "${TMPDIR:-/tmp}/browser-quick-header.XXXXXX")"
if [[ -n "$output" ]]; then
  response_file="$(mktemp "$output_dir/.browser-quick-response.XXXXXX")"
else
  response_file="$(mktemp "${TMPDIR:-/tmp}/browser-quick-response.XXXXXX")"
fi
chmod 600 "$request_file" "$header_file" "$response_file"
printf '%s' "$request_body" >"$request_file"
printf 'Authorization: Bearer %s\n' "$api_token" >"$header_file"

curl_args=(
  --fail-with-body
  --silent
  --show-error
  --connect-timeout "$connect_timeout"
  --max-time "$max_time"
  --request POST
  --header "@$header_file"
  --header 'Content-Type: application/json'
  --data-binary "@$request_file"
  --output "$response_file"
)

curl_status=0
curl --disable "${curl_args[@]}" "$endpoint" || curl_status=$?
if (( curl_status != 0 )); then
  if [[ -s "$response_file" ]]; then
    printf 'browser-quick: response body (up to 8192 bytes):\n' >&2
    head -c 8192 "$response_file" >&2
    printf '\n' >&2
  fi
  exit "$curl_status"
fi

if [[ -n "$expect_min_bytes" ]]; then
  response_bytes="$(wc -c <"$response_file" | tr -d '[:space:]')"
  if (( response_bytes < expect_min_bytes )); then
    semantic_failure "response has $response_bytes bytes; expected at least $expect_min_bytes"
  fi
fi

if (( ${#expect_texts[@]} > 0 )); then
  for expected_text in "${expect_texts[@]}"; do
    if ! LC_ALL=C grep -Fq -- "$expected_text" "$response_file"; then
      semantic_failure "response does not contain one required text value"
    fi
  done
fi

if [[ -n "$output" ]]; then
  mv -f "$response_file" "$output"
else
  cat "$response_file"
fi
