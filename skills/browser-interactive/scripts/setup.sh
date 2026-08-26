#!/usr/bin/env bash
set -euo pipefail

skill_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
npm_cache_dir="${npm_config_cache:-${TMPDIR:-/tmp}/browser-interactive-npm-cache}"

if ! command -v npm >/dev/null 2>&1; then
  printf 'browser-interactive setup: npm is required\n' >&2
  exit 2
fi

cd "$skill_dir"
npm_config_cache="$npm_cache_dir" PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
  npm ci --ignore-scripts --no-audit --no-fund

installed_version="$(node -p "require('./node_modules/playwright-core/package.json').version")"
expected_version="$(node -p "require('./package.json').dependencies['playwright-core']")"
if [[ "$installed_version" != "$expected_version" ]]; then
  printf 'browser-interactive setup: expected playwright-core %s, installed %s\n' \
    "$expected_version" "$installed_version" >&2
  exit 1
fi

printf 'browser-interactive setup: playwright-core %s installed in %s/node_modules\n' \
  "$installed_version" "$skill_dir"
