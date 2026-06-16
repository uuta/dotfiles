---
name: implementation-preflight
description: "Use before starting coding implementation, bug fixes, refactors, feature work, test additions, or engineer-agent handoffs where code or dependencies may change. Choose the implementation strategy first: no-op/delete, reuse existing code or workflows, refactor/extend, stdlib/native feature, already-installed dependency, mature new package/plugin, or minimal new code. Requires current web investigation before adopting any new package/plugin and explicit approval for high-impact dependency or plugin changes."
---

# Implementation Preflight

## Overview

Decide how the change should be built before writing code. The goal is not to minimize effort blindly; it is to avoid parallel implementations, unnecessary dependencies, and hand-rolled solutions where the local codebase, platform, or ecosystem already has the right answer.

Keep the preflight lightweight. For a trivial one-line change, a one-sentence decision is enough. For non-trivial work or any dependency/plugin decision, make the decision explicit before editing or in the first implementation note.

## Workflow

1. Restate the requested behavior and acceptance signal in concrete terms. If the request is already satisfied, say so and avoid changing code.
2. Check local ownership before adding anything:
   - Read applicable local instructions such as `AGENTS.md` and nearby workflow docs.
   - Search for existing code, tests, helpers, commands, skills, or docs with the same responsibility.
   - When available, use `existing-code-first` for the local-code search and `refactoring` for consolidation decisions.
3. Choose the first strategy that fits:
   - no-op or delete code when the behavior is already covered or unnecessary
   - reuse an existing implementation
   - refactor, relocate, or extend the existing owner
   - use a standard library or native platform feature
   - use an already-installed dependency
   - adopt a mature new package/plugin
   - write minimal new code
4. If the strategy requires a new package/plugin, run the adoption gate before installing or enabling it.
5. Implement only the chosen scope. Do not add abstractions, files, config, or workflow changes that the strategy does not require.
6. Verify the behavior with the smallest meaningful check. Non-trivial behavior needs a focused test, command, self-check, or runtime verification.

## Adoption Gate

Do not adopt a new package/plugin from memory. Investigate current sources first.

Required checks:

- Official docs or README: API fit, intended usage, supported framework/runtime versions.
- Package registry metadata: latest version, publish recency, license, dependency footprint.
- Repository health: recent releases or commits, issue activity, maintenance signals.
- Security posture where relevant: advisories, known vulnerabilities, native binaries, install scripts, hooks, or service access.
- Ecosystem fit: whether the current repo/framework already prefers another package or has an installed alternative.
- Runtime/build impact: bundle size, startup cost, config churn, generated code, transitive dependencies, or operational services.

Adopt a mature package/plugin when it clearly beats local implementation for correctness, maintenance, safety, or domain complexity. Prefer this for standardized hard domains such as authentication, payments, date/timezone handling, parsers, rich text, markdown/HTML processing, browser automation, protocol clients, schedulers, diffing, charting, and 3D.

Do not add a package/plugin for simple glue that is clearer as local code.

## Approval Rules

Never silently add or enable high-impact dependencies. Ask for explicit approval before installing or enabling:

- plugins, lifecycle hooks, agent hooks, or shell integration
- runtime dependencies that affect production behavior
- authentication, authorization, security, payment, infrastructure, telemetry, or data-migration packages
- native binaries, install scripts, code generators, framework-level packages, or service-backed SDKs
- packages with unclear license, weak maintenance signals, or broad transitive dependency impact

Low-risk dev/test dependencies or small runtime dependencies may be added during autonomous implementation only when they are clearly scoped, current-source checked, and better than local code. Call them out in the final response or PR summary with the reason, source checked, and verification run.

If web access is unavailable or the investigation cannot establish confidence, do not adopt the new package/plugin. Propose it with the missing evidence and continue with a local or already-installed strategy when feasible.

## Preflight Note

For non-trivial implementation, dependency changes, or agent handoffs, leave a compact note:

```text
Implementation path: reuse | refactor | stdlib/native | installed dependency | new dependency | new code
Evidence checked: <files, commands, docs, or current web sources>
Dependency decision: none | use existing <name> | propose/add <name> because <reason>
Verification: <smallest meaningful check>
```

Keep the note short. The preflight is a decision aid, not a separate planning phase.
