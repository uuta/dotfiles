---
name: acceptance-criteria-clarifier
description: "Clarify requirements when unresolved choices materially change behavior, scope, or verification, or when acceptance criteria are requested."
---

# Acceptance Criteria Clarifier

Resolve uncertainty that would materially change the result. Use the request, prior answers, linked issue, nearby code and conventions before asking the user. Missing template headings alone do not make a task unready.

## Decision boundary

Proceed when the desired behavior is verifiable and local conventions answer the remaining implementation choices. State a consequential, reversible assumption briefly and continue. A task becoming a plan or handoff does not by itself require questions.

Ask when an unresolved choice changes product behavior, compatibility, ownership, persistent data, billing, authorization, or the requested scope and cannot be inferred from the session. Pause only the dependent action and continue useful investigation or independent work.

Prefer one concise question about the decision that matters most. Bundle additional questions only when they are tightly related. Do not ask the user to choose routine implementation details, test commands, or whether to continue work they already requested.

## Acceptance contract

Describe the observable outcome and how to verify it. Scale the detail to the task; a mechanical edit can have a one-sentence acceptance condition.

For an implementation issue or agent handoff, provide enough context to start:

- Goal and required behavior
- Scope and out-of-scope boundaries
- Done when and not done if
- Required blackbox/runtime verification, or a justified alternative
- Blockers, dependencies, accepted deferrals and consequential assumptions

Use the existing issue or project format. Do not create a second contract document unless the workflow needs one. Preserve explicit product decisions and review gates; do not invent new gates simply to fill the template.

Once the meaningful ambiguity is resolved, resume the requested implementation, split, or handoff in the same task. Clarification is not a new approval checkpoint.
