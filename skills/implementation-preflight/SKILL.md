---
name: implementation-preflight
description: "Choose an implementation strategy when reuse, architecture, or a new dependency needs investigation; also supports explicit preflight requests."
---

# Implementation Preflight

Choose an approach when the task presents a real reuse, architecture, or dependency decision. Preserve the requested outcome and existing ownership; do not make a routine edit wait for a separate planning phase.

## Local decision

Read the applicable instructions and enough nearby code, call sites, and tests to locate the behavior's owner. Prefer reusing or extending that owner when it fits. Compare native features, installed dependencies, a mature package, and small local code by correctness and maintenance cost; this is not a mandatory sequence to exhaust.

Use `existing-code-first` only when locating reusable behavior needs deeper investigation, and `refactoring` when consolidation is part of the task. Do not load both automatically. Do not repeat searches already completed in the current task.

For a mechanical edit with a clear owner, proceed directly. Explain consequential choices briefly. If an assignment explicitly requires a preflight note, include:

```text
Implementation path: <chosen approach>
Evidence checked: <relevant files or sources>
Dependency decision: <none, existing, or proposed addition and reason>
Verification: <observable acceptance check>
```

## New dependency or plugin

Before adopting one, check current official documentation for API/runtime compatibility, licensing and maintenance. Inspect install scripts, native code, service access, security advisories and runtime cost when they affect the decision. Do not infer package suitability from familiarity alone.

Prefer a maintained package for complex standardized behavior when it improves correctness and maintenance. Keep simple glue local. If evidence is unavailable, continue with an existing/native approach when feasible; report the unresolved adoption decision.

## Authorization boundary

Use authorization already present in the request. An explicit request to install or integrate a named dependency does not need approval again for that same action. Routine, reversible, scoped dependency changes can proceed with a brief explanation.

Before an additional action changes privileges, activates hooks or shell integrations, introduces a paid service, migrates persistent data, or changes production infrastructure, establish that this effect is authorized. If it is not, prepare the concrete diff and impact first, then ask about that action. Reading documentation and preparing local changes can continue.

## Completion

Implement the chosen scope and run the relevant acceptance check and repository-required checks. Repair failures caused by the change and rerun affected checks. Expand verification only for a concrete uncovered risk or explicit requirement; report environmental gaps separately from regressions.
