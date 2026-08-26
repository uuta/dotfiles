#!/usr/bin/env bash
set -euo pipefail

test_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
browser_quick="$test_dir/../scripts/browser-quick.sh"
case_count=0

assert_route() {
  local expected_browser="$1"
  shift

  local result actual_browser endpoint
  result="$("$browser_quick" "$@" --dry-run)"
  actual_browser="$(jq -r '.browser' <<<"$result")"
  endpoint="$(jq -r '.endpoint' <<<"$result")"

  if [[ "$actual_browser" != "$expected_browser" ]]; then
    printf 'expected browser %s, got %s for: %s\n' "$expected_browser" "$actual_browser" "$*" >&2
    exit 1
  fi

  if [[ "$expected_browser" == "kitesurf" ]]; then
    [[ "$endpoint" == *'?browser=kitesurf' ]] || {
      printf 'Kitesurf endpoint is missing its query parameter: %s\n' "$endpoint" >&2
      exit 1
    }
  elif [[ "$endpoint" == *'browser=kitesurf'* ]]; then
    printf 'Chromium endpoint unexpectedly selects Kitesurf: %s\n' "$endpoint" >&2
    exit 1
  fi

  case_count=$((case_count + 1))
}

assert_route kitesurf markdown --url https://example.com
assert_route chromium screenshot --url https://example.com
assert_route kitesurf screenshot --url https://example.com --browser kitesurf
assert_route chromium markdown --url https://example.com --browser chromium

assert_route kitesurf content --url https://example.com
assert_route kitesurf links --url https://example.com
assert_route kitesurf scrape --url https://example.com --data '{"elements":[{"selector":"h1"}]}'
assert_route kitesurf accessibilityTree --url https://example.com
assert_route kitesurf json --url https://example.com --data '{"prompt":"Extract the title"}'
assert_route chromium pdf --url https://example.com
assert_route chromium snapshot --url https://example.com

printf 'ok - %d browser routing cases\n' "$case_count"
