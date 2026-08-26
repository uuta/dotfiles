#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const skillDir = path.resolve(scriptDir, "..");
const setupCommand = path.join(skillDir, "scripts", "setup.sh");

function usage() {
  process.stdout.write(`Usage:
  run-task.mjs [--project DIR] [--target cloudflare|local]
               [--browser chromium|firefox|webkit] [--headed]
               [--storage-state FILE] [--output-dir DIR]
               [--keep-alive-ms N] [--timeout-ms N] TASK_MODULE

TASK_MODULE must export an async default function or named run function.
TASK_MODULE is trusted, unsandboxed Node.js code.
`);
}

function fail(message) {
  process.stderr.write(`browser-interactive: ${message}\n`);
  process.exit(2);
}

const options = {
  project: process.cwd(),
  target: "cloudflare",
  browser: "chromium",
  headed: false,
  storageState: undefined,
  outputDir: path.resolve(process.cwd(), "test-results/browser-task"),
  keepAliveMs: 60_000,
  timeoutMs: 120_000,
};

const args = process.argv.slice(2);
let taskPath;

for (let index = 0; index < args.length; index += 1) {
  const argument = args[index];
  const value = () => {
    index += 1;
    if (index >= args.length) fail(`${argument} requires a value`);
    return args[index];
  };

  switch (argument) {
    case "--project": options.project = path.resolve(value()); break;
    case "--target": options.target = value(); break;
    case "--browser": options.browser = value(); break;
    case "--headed": options.headed = true; break;
    case "--storage-state": options.storageState = path.resolve(value()); break;
    case "--output-dir": options.outputDir = path.resolve(value()); break;
    case "--keep-alive-ms": options.keepAliveMs = Number(value()); break;
    case "--timeout-ms": options.timeoutMs = Number(value()); break;
    case "-h":
    case "--help": usage(); process.exit(0); break;
    default:
      if (argument.startsWith("-")) fail(`unknown argument: ${argument}`);
      if (taskPath) fail("provide exactly one task module");
      taskPath = path.resolve(argument);
  }
}

if (!taskPath) fail("provide a task module");
if (!fs.existsSync(taskPath)) fail(`task module not found: ${taskPath}`);
if (!fs.existsSync(options.project)) fail(`project directory not found: ${options.project}`);
if (!["cloudflare", "local"].includes(options.target)) fail(`unsupported target: ${options.target}`);
if (!["chromium", "firefox", "webkit"].includes(options.browser)) fail(`unsupported browser: ${options.browser}`);
if (!Number.isInteger(options.keepAliveMs) || options.keepAliveMs < 0 || options.keepAliveMs > 600_000) {
  fail("--keep-alive-ms must be an integer from 0 through 600000");
}
if (!Number.isInteger(options.timeoutMs) || options.timeoutMs < 1 || options.timeoutMs > 3_600_000) {
  fail("--timeout-ms must be an integer from 1 through 3600000");
}
if (options.target !== "local" && options.browser !== "chromium") {
  fail("Cloudflare CDP targets require --browser chromium");
}
if (options.target !== "local" && options.headed) fail("--headed is local-only");
if (options.target !== "local" && options.storageState) fail("--storage-state is local-only");
if (options.storageState && !fs.existsSync(options.storageState)) fail(`storage state not found: ${options.storageState}`);

let playwright;
let loadedPackage;

if (options.target === "cloudflare") {
  const skillRequire = createRequire(path.join(skillDir, "package.json"));
  try {
    playwright = skillRequire("playwright-core");
    loadedPackage = "playwright-core";
  } catch (error) {
    if (error?.code !== "MODULE_NOT_FOUND") throw error;
    fail(`shared playwright-core is not installed; run ${setupCommand}`);
  }
} else {
  const projectRequire = createRequire(path.join(options.project, "package.json"));
  for (const packageName of ["playwright", "@playwright/test", "playwright-core"]) {
    let resolvedPackage;
    try {
      resolvedPackage = projectRequire.resolve(packageName);
    } catch (error) {
      if (error?.code !== "MODULE_NOT_FOUND") throw error;
      continue;
    }

    playwright = projectRequire(resolvedPackage);
    loadedPackage = packageName;
    break;
  }

  if (!playwright) {
    fail(`Playwright is not installed in ${options.project}; install the repository's chosen package explicitly`);
  }
}

const cloudflareAccountId = process.env.CLOUDFLARE_ACCOUNT_ID ?? process.env.CF_ACCOUNT_ID;
const cloudflareApiToken = process.env.CLOUDFLARE_API_TOKEN ?? process.env.CF_API_TOKEN;
if (options.target !== "local") {
  if (!cloudflareAccountId) fail("set CLOUDFLARE_ACCOUNT_ID or CF_ACCOUNT_ID");
  if (!cloudflareApiToken) fail("set CLOUDFLARE_API_TOKEN or CF_API_TOKEN");
  delete process.env.CLOUDFLARE_API_TOKEN;
  delete process.env.CF_API_TOKEN;
}

const credentialValues = [cloudflareAccountId, cloudflareApiToken].filter(Boolean);

function redactCredentials(value) {
  let redacted = String(value);
  for (const credential of credentialValues) redacted = redacted.replaceAll(credential, "[redacted]");
  return redacted;
}

function redactError(error, seen = new Set()) {
  if (!(error instanceof Error) || seen.has(error)) return error;
  seen.add(error);
  error.message = redactCredentials(error.message);
  if (typeof error.stack === "string") error.stack = redactCredentials(error.stack);
  if (error.cause) redactError(error.cause, seen);
  if (error instanceof AggregateError) {
    for (const nestedError of error.errors) redactError(nestedError, seen);
  }
  return error;
}

const taskModule = await import(pathToFileURL(taskPath).href);
const run = taskModule.run ?? taskModule.default;
if (typeof run !== "function") fail("task module must export an async default function or named run function");

fs.mkdirSync(options.outputDir, { recursive: true });

let browser;
let context;
let remoteSessionId;
let resourceAcquisition;
let cleanupPromise;
const cleanupTimeoutMs = 5_000;
const cloudflareApiBase = options.target === "cloudflare"
  ? `https://api.cloudflare.com/client/v4/accounts/${encodeURIComponent(cloudflareAccountId)}/browser-rendering/devtools/browser`
  : undefined;

async function closeWithTimeout(label, close) {
  let timeoutHandle;
  try {
    await Promise.race([
      Promise.resolve().then(close),
      new Promise((_, reject) => {
        timeoutHandle = setTimeout(() => reject(new Error(`${label} cleanup timed out after ${cleanupTimeoutMs} ms`)), cleanupTimeoutMs);
      }),
    ]);
  } finally {
    clearTimeout(timeoutHandle);
  }
}

async function cleanup() {
  if (cleanupPromise) return cleanupPromise;
  cleanupPromise = (async () => {
    const errors = [];
    if (context && options.target === "local") {
      try {
        await closeWithTimeout("context", () => context.close());
      } catch (error) {
        errors.push(redactError(new Error(`context cleanup failed: ${error.message}`, { cause: error })));
      }
    }
    if (browser) {
      try {
        await closeWithTimeout("browser", () => browser.close());
      } catch (error) {
        errors.push(redactError(new Error(`browser cleanup failed: ${error.message}`, { cause: error })));
      }
    }
    if (remoteSessionId) {
      try {
        await closeWithTimeout("Cloudflare session", async () => {
          const response = await fetch(`${cloudflareApiBase}/${encodeURIComponent(remoteSessionId)}`, {
            method: "DELETE",
            headers: { Authorization: `Bearer ${cloudflareApiToken}` },
            signal: AbortSignal.timeout(cleanupTimeoutMs),
          });
          if (!response.ok && response.status !== 404) {
            throw new Error(`Cloudflare API returned ${response.status} ${response.statusText}`);
          }
        });
      } catch (error) {
        errors.push(redactError(new Error(`Cloudflare session cleanup failed: ${error.message}`, { cause: error })));
      }
    }
    return errors;
  })();
  return cleanupPromise;
}

let terminationSignal;
for (const signal of ["SIGHUP", "SIGINT", "SIGTERM"]) {
  process.once(signal, async () => {
    if (terminationSignal) return;
    terminationSignal = signal;
    try {
      await resourceAcquisition;
    } catch {
      // Cleanup below owns any resource that was acquired before the failure.
    }
    const errors = await cleanup();
    for (const error of errors) process.stderr.write(`browser-interactive: ${error.message}\n`);
    const exitCodes = { SIGHUP: 129, SIGINT: 130, SIGTERM: 143 };
    process.exit(exitCodes[signal]);
  });
}

let result;
let primaryError;
try {
  resourceAcquisition = (async () => {
    if (options.target === "local") {
      browser = await playwright[options.browser].launch({ headless: !options.headed, timeout: 30_000 });
      if (terminationSignal) return;
      context = await browser.newContext({
        ...(options.storageState ? { storageState: options.storageState } : {}),
      });
      return;
    }

    const query = new URLSearchParams();
    if (options.keepAliveMs > 0) query.set("keep_alive", String(options.keepAliveMs));
    const createEndpoint = query.size > 0 ? `${cloudflareApiBase}?${query}` : cloudflareApiBase;
    const createResponse = await fetch(createEndpoint, {
      method: "POST",
      headers: { Authorization: `Bearer ${cloudflareApiToken}` },
      signal: AbortSignal.timeout(30_000),
    });
    if (!createResponse.ok) {
      throw new Error(`Cloudflare session creation failed: ${createResponse.status} ${createResponse.statusText}`);
    }
    const createPayload = await createResponse.json();
    const session = createPayload.result ?? createPayload;
    if (typeof session.sessionId !== "string" || session.sessionId.length === 0) {
      throw new Error("Cloudflare session creation returned no session ID");
    }
    remoteSessionId = session.sessionId;
    if (terminationSignal) return;

    const endpoint = session.webSocketDebuggerUrl
      ?? `wss://api.cloudflare.com/client/v4/accounts/${encodeURIComponent(cloudflareAccountId)}/browser-rendering/devtools/browser/${encodeURIComponent(remoteSessionId)}`;
    browser = await playwright.chromium.connectOverCDP(endpoint, {
      headers: { Authorization: `Bearer ${cloudflareApiToken}` },
      timeout: 30_000,
    });
    if (terminationSignal) return;
    context = browser.contexts()[0] ?? await browser.newContext();
  })();
  await resourceAcquisition;
  if (terminationSignal) throw new Error(`terminated by ${terminationSignal}`);

  const page = context.pages()[0] ?? await context.newPage();
  let timeoutHandle;
  const timeout = new Promise((_, reject) => {
    timeoutHandle = setTimeout(() => {
      reject(new Error(`task timed out after ${options.timeoutMs} ms`));
    }, options.timeoutMs);
  });
  try {
    result = await Promise.race([
      Promise.resolve(run({
        browser,
        context,
        page,
        outputDir: options.outputDir,
        target: options.target,
        playwrightPackage: loadedPackage,
      })),
      timeout,
    ]);
  } finally {
    clearTimeout(timeoutHandle);
  }
} catch (error) {
  primaryError = error;
}

const cleanupErrors = await cleanup();
if (primaryError) {
  for (const error of cleanupErrors) process.stderr.write(`browser-interactive: ${error.message}\n`);
  throw redactError(primaryError);
}
if (cleanupErrors.length > 0) {
  throw new AggregateError(cleanupErrors, "browser cleanup failed");
}
if (result !== undefined) {
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}
