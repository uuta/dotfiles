#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  playwright-cli.sh [--project DIR] -- PLAYWRIGHT_ARGS...

Runs an existing Playwright CLI without installing packages.
USAGE
}

die() {
  printf 'playwright-cli: %s\n' "$*" >&2
  exit 2
}

project="$PWD"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)
      [[ $# -ge 2 ]] || die "--project requires a value"
      project="$2"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *) die "unknown wrapper argument: $1 (place Playwright arguments after --)" ;;
  esac
done

[[ -d "$project" ]] || die "project directory not found: $project"
[[ $# -gt 0 ]] || die "provide Playwright arguments after --"

project="$(cd "$project" && pwd -P)"
local_cli="$project/node_modules/.bin/playwright"
local_core_cli="$project/node_modules/.bin/playwright-core"

if [[ -x "$local_cli" ]]; then
  cd "$project"
  exec "$local_cli" "$@"
fi

if [[ -x "$local_core_cli" ]]; then
  cd "$project"
  exec "$local_core_cli" "$@"
fi

if command -v playwright >/dev/null 2>&1; then
  cd "$project"
  exec playwright "$@"
fi

if command -v playwright-core >/dev/null 2>&1; then
  cd "$project"
  exec playwright-core "$@"
fi

die "Playwright is not installed in $project; install the repository's chosen Playwright package explicitly"
