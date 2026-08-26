---
name: browser-quick
description: Fetch or render a web page as a one-shot result without interactive browser control. Use for HTML, Markdown, screenshots, PDFs, accessibility trees, links, selector-based scraping, snapshots, or structured JSON extraction. Route structured extraction to Kitesurf and visually faithful or dynamic rendering to Cloudflare Chromium, with one Chromium fallback after a Kitesurf semantic or visual failure.
---

# Browser Quick

Return one result through Cloudflare Quick Actions. Keep the Kitesurf-versus-Chromium choice internal; do not ask the user to select an engine. Do not start Playwright, a local browser, or an MCP server.

## Route the task

- Use this skill for one-shot input-to-output work.
- Use Kitesurf by default for structured extraction: `content`, `markdown`, `links`, `scrape`, `accessibilityTree`, and `json`.
- Use Chromium by default for visual output: `screenshot`, `pdf`, and `snapshot`. A snapshot can contain a screenshot, so treat it as visual even when requesting other formats too.
- For any action on a video site, SPA, advertisement- or hydration-dependent page, or a site already known to render incorrectly in Kitesurf, select Chromium on the first attempt with `--browser chromium`. YouTube and Nico Nico are measured examples; do not maintain a domain denylist in the wrapper.
- Always honor an explicit `--browser kitesurf|chromium`; it overrides the action-aware wrapper default.
- Use `browser-interactive` for clicks, form entry, waits, multi-step navigation, E2E assertions, localhost, persistent authentication, WebGL, playback control, or detailed browser control.
- Prefer `content`, `markdown`, `links`, or `scrape` over screenshots when structured text is sufficient.
- Treat `json` as an AI-backed endpoint with separate Workers AI usage.
- Use Cloudflare's dedicated crawl workflow separately when site-wide asynchronous crawling is required; this Skill does not poll crawl jobs.

## Prepare credentials

Require these environment variables; never write their values into the skill, dotfiles, commands shown to the user, or output artifacts:

```sh
export CLOUDFLARE_ACCOUNT_ID="..."
export CLOUDFLARE_API_TOKEN="..."
```

`CF_ACCOUNT_ID` and `CF_API_TOKEN` are accepted aliases. The token needs `Browser Rendering - Edit` permission.

## Run an action

Use `~/dotfiles/skills/browser-quick/scripts/browser-quick.sh` instead of reconstructing curl commands. It accepts a URL or merges a supplied JSON object with that URL.

```sh
~/dotfiles/skills/browser-quick/scripts/browser-quick.sh markdown --url https://example.com

~/dotfiles/skills/browser-quick/scripts/browser-quick.sh screenshot \
  --url https://example.com \
  --data '{"screenshotOptions":{"fullPage":true}}' \
  --output screenshot.png

~/dotfiles/skills/browser-quick/scripts/browser-quick.sh content \
  --url https://www.youtube.com/ \
  --browser chromium

~/dotfiles/skills/browser-quick/scripts/browser-quick.sh scrape \
  --url https://example.com \
  --data '{"elements":[{"selector":"h1"}]}'

~/dotfiles/skills/browser-quick/scripts/browser-quick.sh json \
  --url https://example.com \
  --data '{"prompt":"Extract the page title"}'
```

The `json` action requires either a non-empty `prompt` or a `response_format` containing `type: "json_schema"` and a `json_schema` object.

Use `--html-file` for local HTML and `--data-file` for complex or sensitive request bodies. Avoid inline cookies, authorization headers, and passwords because shell history and process listings may expose them. Store sensitive JSON in a permission-restricted temporary file and remove it after use.

For binary actions (`screenshot` and `pdf`), always pass `--output`. For other actions, redirect stdout to a task artifact when the result must be preserved.

Use `--dry-run` to verify the selected browser, endpoint, required fields, and request keys without sending a request. It never prints request or credential values.

The default connection timeout is 15 seconds and the total request timeout is 120 seconds. Override them with `--connect-timeout SECONDS` and `--max-time SECONDS` when a known action requires different bounds.

## Define success before running

For text responses, pass known invariants to the wrapper instead of accepting HTTP success alone. `--expect-text TEXT` is repeatable and checks literal text. `--expect-min-bytes N` works for text and binary responses. A failed semantic check exits with status 65 and does not publish `--output`.

```sh
~/dotfiles/skills/browser-quick/scripts/browser-quick.sh markdown \
  --url https://example.com \
  --expect-text "Example Domain" \
  --expect-min-bytes 100
```

For screenshots and PDFs, set a reasonable `--expect-min-bytes` and inspect the rendered artifact. A skeleton screen, persistent loading placeholder, blank primary content region, missing requested selector/content, or wrong authenticated state is a failure even if the HTTP request succeeded.

## Verify and fall back

1. Check the `--dry-run` browser before the real request when route choice matters.
2. Check the exit status. Status 65 means the response failed a declared semantic check. The script publishes `--output` atomically only after both transport and semantic success.
3. Parse JSON responses with `jq` when applicable and verify task-specific fields.
4. Always inspect screenshots or PDFs when their visual content is the requested result.
5. If a Kitesurf attempt returns status 65, a skeleton/blank visual result, unsupported behavior, or materially different rendering, rerun exactly once with `--browser chromium`. Do not ask the user to choose the engine or retry Kitesurf for the same incompatibility.
6. If one-shot Chromium still cannot express the workflow, move to `browser-interactive`. It chooses Cloudflare Chromium for public sites and a local browser for localhost.
7. Never automatically replay an action that can submit, publish, purchase, delete, send, or otherwise mutate external state. Confirm whether the first attempt took effect before any retry.

Quick Actions are ephemeral except for documented caching, crawl retention, or explicitly enabled recording. Do not infer that remote processing means no data leaves the machine.
