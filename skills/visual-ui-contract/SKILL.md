---
name: visual-ui-contract
description: Create and enforce visual contracts for screenshot-driven UI work. Use when a task includes approved screenshots, mockups, ideal images, visual fidelity requirements, golden/screenshot tests, or when splitting/reviewing UI work where agents must preserve an intended layout.
---

# Visual UI Contract

## Purpose

Use this skill to turn an approved UI image into an enforceable implementation contract. The contract should guide task splitting, agent assignment, and review so agents cannot satisfy behavior while drifting from the intended UI.

Do not use this skill for ordinary UI wiring, copy changes, button behavior, or non-visual refactors unless the issue already has a visual contract or approved reference image.

## Core Rules

- Treat the approved image as input to a testable visual contract, not as decoration in the parent issue.
- Create the draft UI component and visual regression gate before behavior integration.
- Keep visual shell/component composition together when splitting them would let later agents assemble a different UI.
- Let non-visual service/model/action tasks run in parallel only if they do not touch layout, styling, or visual baselines.
- Make integration tasks depend on the approved visual shell.
- Put old UI cleanup after replacement UI is mounted and visually verified.
- If a visual/golden/screenshot test fails, fix implementation code.
- Do not update golden images, snapshots, screenshot baselines, thresholds, test selectors, or visual expectations unless the user explicitly approves a baseline change.
- If the expected UI seems obsolete, stop and ask.

## Visual Contract Contents

Extract only durable invariants that matter for the product. Do not require pixel-perfect matching unless the user explicitly asks.

Include:

- Reference image/source URL and target screen/state.
- Component scope: shell, composed content, integration surface.
- Layout invariants: placement, sheet height, spacing, grouping, alignment, z-order, scrolling/collapse behavior.
- Visual treatment: background dimming, color role, typography weight, border/radius/elevation, icon/button style.
- Content contract: required labels, placeholder behavior for missing data, button set, removed legacy elements.
- Interaction contract: drag/collapse/close/share/link behavior if it is visually coupled.
- Test contract: golden/screenshot/component tests to protect the contract.
- Baseline integrity rule: no baseline/threshold/selector edits without user approval.

## Task Split Pattern

When splitting a screenshot-driven UI PBI, produce this dependency shape:

```text
A. Visual contract / draft UI component
   Create mock-data UI, stable keys, and visual regression gate.

B. Non-visual parallel tasks
   Models, URL builders, action services, provider seams, test helpers.
   These must not alter layout or approved visual baselines.

C. Integration tasks
   Mount the visual component into real flows and wire state/actions.
   These depend on A and any required B tasks.

D. Cleanup tasks
   Remove old modal/wrapper/legacy UI after integration is visually verified.
```

Prefer the first task to be `Visual shell - <component>` rather than a generic component task. It should own both the mock-data component composition and the visual test. Splitting shell and visual test into separate tasks is allowed only when the visual test task blocks all later UI integration.

## Sub-Issue Requirements

For the first visual shell task, include:

- Scope: implement mock-data UI matching the approved reference.
- Work: component layout, mock data rendering, stable keys, test harness.
- Tests: golden/screenshot or component-level visual regression.
- Done when: visual artifact matches the approved contract and test fails on meaningful layout/style drift.
- Not done if: only widget-existence tests are added, thresholds are broad, or baselines are changed without approval.

For later UI integration tasks, include:

- Dependency on the visual shell task.
- Rule: do not modify golden baselines, visual snapshots, thresholds, selectors, or visual expectations.
- Verification: run the visual regression test and provide screenshot/golden evidence when possible.
- Not done if: the feature works but the approved visual contract regresses.

## Agent Assignment Block

Paste this into implementation prompts for visual-contract tasks:

```text
Visual contract rules:
- The approved screenshot/mockup is a binding UI contract.
- Preserve layout, spacing, typography weight, button placement, sheet height, background treatment, and removed legacy UI noted in the issue.
- Run the visual/golden/screenshot tests listed in the issue.
- If visual tests fail, fix implementation code.
- Do not update golden images, snapshots, screenshot baselines, thresholds, test selectors, or visual expectations unless the user explicitly approves a baseline change.
- If you believe the visual baseline is obsolete, stop and ask.
- Provide the captured screenshot/golden result or explain why capture is blocked.
```

## Review Gate

For visual-contract work, do not mark review clean from code diff alone.

Check:

- The visual contract task exists before integration/cleanup tasks.
- The diff includes or preserves an executable visual regression gate.
- The implementation did not weaken baselines, thresholds, selectors, or visual assertions.
- Screenshot/golden evidence exists, or the lack of it is an explicit blocker/accepted deferral.
- Existing behavior tests passing is not enough if the visual contract is unverified.

Classify as `fix_required` when an agent changes implementation correctly but omits the visual gate or weakens baseline integrity.
