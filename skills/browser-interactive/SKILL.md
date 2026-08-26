---
name: browser-interactive
description: Interactively automate and verify browser workflows with Playwright. Use for waits, clicks, forms, authenticated flows, multi-step navigation, localhost, E2E assertions, or any task requiring control between page load and result. Use Cloudflare Chromium for public sites by default and a local browser for localhost or repository-local E2E behavior.
---

# Browser Interactive

Run Playwright only for the duration of the task. Do not start `@playwright/mcp` or another persistent server unless the user explicitly requests interactive MCP tools.

Use Playwright as the control layer. Keep runtime selection internal: use Cloudflare Chromium for public sites unless the task requires local execution; use a local browser for localhost, repository E2E tests, headed debugging, or local storage state. Do not ask the user to select a target unless the choice changes the requested behavior.

## Choose the lightest path

1. Use `browser-quick` when one stateless result is sufficient.
2. Reuse the repository's existing Playwright tests, config, fixtures, commands, and installed package for repository-local E2E work.
3. For repository-local tests or local CLI screenshots, run the repository's Playwright CLI through `scripts/playwright-cli.sh`.
4. For a public-site workflow, or any custom multi-step workflow, write a small task module and run it through `scripts/run-task.mjs`; it defaults to Cloudflare Chromium and owns browser cleanup.

Do not add Playwright to a project silently. Local execution requires the repository's own `playwright`, `@playwright/test`, or `playwright-core` installation. Report a missing local dependency and ask before installing it. Do not use `npx -y`, which can download packages implicitly.

## Run the one-time machine setup

Before the first Cloudflare task on a machine, explicitly run the idempotent setup script:

```sh
~/dotfiles/skills/browser-interactive/scripts/setup.sh
```

The script installs only the pinned, browserless `playwright-core` control library under this skill. Normal task execution never installs packages or browser binaries. If setup has not run, `run-task.mjs` stops with the setup command instead of falling back to a local browser.

## Select the runtime internally

- For a public URL, use the default Cloudflare Chromium target. The browser process runs on Cloudflare; only Node.js and the skill-local Playwright client run locally. This runtime works from projects that have no Playwright dependency.
- For localhost, exact local app behavior, repository E2E tests, headed debugging, or local storage state, pass `--target local`. Launch a clean, temporary context and never attach to the user's everyday Chrome profile.

For remote targets, require `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` (or `CF_ACCOUNT_ID` and `CF_API_TOKEN`). Never place tokens in source files or command arguments.

## Use the existing CLI for local project work

Pass normal Playwright CLI arguments after `--`:

```sh
~/dotfiles/skills/browser-interactive/scripts/playwright-cli.sh \
  --project "$PWD" -- test tests/example.spec.ts

~/dotfiles/skills/browser-interactive/scripts/playwright-cli.sh \
  --project "$PWD" -- screenshot https://example.com screenshot.png
```

The wrapper uses only a project-local or already available Playwright executable. It accepts the `playwright` binary from `playwright`/`@playwright/test` and the `playwright-core` binary from `playwright-core`. It does not install anything.

## Run a managed task module

Create a temporary `.mjs` module that exports `run` or a default async function. Receive `{ browser, context, page, outputDir, target }` and perform only the task-specific steps:

```js
export async function run({ page, outputDir }) {
  await page.goto("https://example.com", { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: "Example Domain" }).waitFor();
  await page.screenshot({ path: `${outputDir}/example.png`, fullPage: true });
  return { title: await page.title() };
}
```

Run it with:

```sh
node ~/dotfiles/skills/browser-interactive/scripts/run-task.mjs \
  --project "$PWD" \
  --output-dir ./test-results/browser-task \
  /absolute/path/to/task.mjs
```

The task module is trusted, unsandboxed Node.js code. Read it before running it; it can access the filesystem and network. On remote targets the runner removes Cloudflare API-token variables from the task module's environment before importing it.

Important options:

- `--target local`, `--headed`, `--storage-state FILE`, and `--browser firefox|webkit` are advanced local-execution options. Treat storage-state files as secrets.
- `--keep-alive-ms N` controls the Cloudflare inactivity window and accepts 0–600000 milliseconds.
- `--timeout-ms N` bounds the complete task function; the default is 120000 milliseconds.

Each remote invocation acquires a new Browser Run session and uses its default CDP context. The runner disconnects Playwright and explicitly deletes the Cloudflare session on success, task failure, timeout, or a catchable termination signal. Local runs close their context and browser under the same conditions. Cleanup failures are reported instead of silently treated as success.

## Verify

- Prefer role, label, text, and test-id locators over brittle CSS or coordinate clicks.
- Assert the intended state, not merely successful navigation.
- Save screenshots, traces, or other evidence under the repository's existing test artifact directory when one exists.
- Inspect visual output when appearance matters.
- On failure, preserve the first useful error and artifact; do not blindly retry state-changing actions.
- Do not use browser automation to submit, purchase, publish, delete, or send externally unless the user authorized that action.
