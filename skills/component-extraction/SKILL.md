---
name: component-extraction
description: Use when a UI change, bug fix, or review touches repeated inline UI blocks and Codex should decide whether to extract a small presentational domain component. Helps identify repeated UI with shared visual or interaction responsibility, keep domain state management in callers, define explicit component state such as enabled/disabled, and avoid over-extracting generic atoms.
---

# Component Extraction

## Overview

Extract repeated UI into presentational components when it reduces duplication and centralizes visual and interaction semantics. Keep domain state, data fetching, provider access, and orchestration in the caller.

## Workflow

1. Find repeated UI with `rg` and inspect every call site before extracting.
2. Confirm the repetition has shared domain responsibility, not only the same low-level widgets.
3. Define the component boundary:
   - The component owns drawing, visual state, interaction affordance, semantic label, stable size, shape, and icon.
   - The caller owns domain state, provider reads, notifier calls, callbacks, positioning, layout, and data fetching.
4. Prefer a domain name when the behavior is domain-specific, such as `LocationRequestFab`, instead of a generic atom name.
5. Give the component an explicit API:
   - Accept a state enum or clear input such as `enabled`, `disabled`, `idle`, or `requesting`.
   - Accept callbacks from the caller. Use nullable callbacks only if that matches the local codebase pattern.
   - Do not read providers, notifiers, repositories, or services inside the presentational component.
   - Use theme-derived colors inside the component so call sites do not repeat ad hoc color logic.
6. Update call sites to pass state and callbacks from their existing domain logic.
7. Add or update focused tests near the changed layer:
   - Component/widget tests for disabled visuals and tap behavior when feasible.
   - Caller tests for domain state mapping, such as `isLoading` becoming disabled, when practical.
   - Do not update visual baselines or golden images unless that visual change is expected and approved.

## Decision Checklist

Extract when two or more UI blocks share the same domain responsibility and new visual or interaction behavior would otherwise be copied.

Do not extract when there is only one usage, the duplication is incidental with different semantics, or the extraction would force the component to manage domain state.

Avoid generic atoms when the component exists because of a product concept. A small domain component is usually clearer than a reusable primitive with unclear ownership.

## Review Checklist

Flag these issues during review:

- The extracted component reads providers, notifiers, repositories, or services.
- The caller still repeats disabled colors, icon styling, shape, or semantics that should belong to the component.
- The component owns screen positioning or layout that differs between call sites.
- A disabled visual state exists but `onPressed` or the equivalent interaction remains active.
- The component API exposes raw booleans that are already becoming ambiguous; prefer an enum once there are multiple meaningful states.

## Example

```dart
LocationRequestFab(
  state: locationState.isLoading
      ? LocationRequestFabState.disabled
      : LocationRequestFabState.enabled,
  onPressed: () => locationNotifier.getSimpleCity(token),
)
```

Good split: the caller reads `LocationState.isLoading` and decides the state; the component maps that state to colors, semantics, and tap behavior.
