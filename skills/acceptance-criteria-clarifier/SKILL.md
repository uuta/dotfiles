---
name: acceptance-criteria-clarifier
description: "Clarify ambiguous implementation requests into explicit, testable acceptance criteria before coding, issue splitting, agent delegation, or review. Use when success is vague, scope or out-of-scope is missing, multiple valid interpretations exist, blackbox/runtime verification is unclear, risky assumptions are needed, or the user asks to make requirements or acceptance criteria explicit. Avoid using for trivial mechanical edits where the requested outcome is already objectively verifiable."
---

# Acceptance Criteria Clarifier

Use this skill as a readiness gate. The goal is to convert ambiguity into an explicit acceptance contract without bothering the user for decisions that are already clear from the request or local context.

## Trigger Gate

Use the skill when any of these are true:

- The request uses vague success words such as "improve", "support", "handle", "properly", "better", "polish", "etc.", "as needed", or "make it work" without examples.
- Scope, out-of-scope, target users, inputs, outputs, error behavior, or compatibility expectations are missing and could change the implementation.
- There are multiple plausible product behaviors or technical contracts, and choosing one silently would create rework.
- The task will be delegated to another agent, split into an issue, turned into a plan, or used as a review gate.
- The task crosses boundaries such as UI/API, CLI/runtime, storage/schema, auth/ownership, external service integration, migrations, or deployment behavior.
- The user explicitly asks to define requirements, acceptance criteria, a contract, ready state, done-when, not-done-if, or blackbox verification.

Do not use the skill for:

- Small mechanical edits with a named file or exact behavior that can be directly verified.
- Failing tests or CI fixes where the failure output already defines the acceptance target.
- Direct factual questions, shell commands, formatting-only changes, or code review unless the review requires reconstructing unclear acceptance criteria.
- Tasks where existing repo conventions clearly answer the missing details and the risk of being wrong is low.

## Hard Stop Rules

Stop and ask clarification before implementation, issue creation, or agent handoff when:

- There is no testable definition of success.
- The implementation could reasonably satisfy the request in two or more incompatible ways.
- The missing decision affects public behavior, data shape, persistence, auth, migration, billing, deletion, external integrations, or UI flow.
- The requested outcome cannot be verified by blackbox/runtime behavior, tests, screenshots, logs, or another concrete artifact.
- "Done" is defined only by intent, such as "works well" or "is clean", rather than observable behavior.

Proceed with clearly labeled assumptions only when:

- The work is low-risk, reversible, and local.
- Existing code, docs, or tests make the intended behavior obvious.
- The user explicitly says to proceed with assumptions.
- The useful next step is investigation only, not implementation or delegation.

When proceeding with assumptions, state them briefly and include them in the final acceptance contract.

## Clarification Workflow

1. Extract what is already known from the user request, linked issue, docs, tests, screenshots, and local code before asking.
2. Build an internal missing-list across goal, scope, out-of-scope, requirements, done-when, not-done-if, blockers, and verification.
3. Ask a compact batch of only the missing questions. Prefer 3-6 questions. Do not ask about fields already answered.
4. Make questions concrete. Offer a recommended default when one is reasonable, and make the tradeoff visible.
5. After the user responds, remove answered items from the missing-list. Ask follow-up questions only for contradictions, newly exposed gaps, or answers that still are not testable.
6. Stop asking when the acceptance contract passes the explicitness checklist.
7. Produce the final contract, or state that the work is not ready and name the exact unresolved blockers.

Be critical. Do not accept broad statements as acceptance criteria when examples, boundaries, or verification are still missing.

## Question Quality

Ask questions that force implementation-relevant choices:

- Bad: "Should this be good?"
- Better: "Which behavior is accepted when the input is invalid: reject with a validation error, skip the row, or preserve current behavior?"

- Bad: "Do you want tests?"
- Better: "What blackbox signal should prove this is done: CLI output, API response, UI state, screenshot, generated file, log line, or a specific command?"

- Bad: "Any edge cases?"
- Better: "Should empty input, duplicate input, and missing permissions be in scope for this change, or explicitly out of scope?"

Avoid repeating a question once the user has answered it. If the answer is partial, ask only for the missing part.

## Explicitness Checklist

Acceptance criteria are explicit enough only when all applicable items are true:

- The user-visible behavior or externally observable outcome is concrete.
- Scope and out-of-scope are separated.
- Success conditions and failure conditions are testable.
- Inputs, outputs, state changes, and important errors are named.
- Blackbox/runtime verification is possible, or a justified alternative verification artifact is named.
- Blockers, dependencies, and accepted deferrals are called out.
- Risky assumptions are either confirmed by the user or clearly marked as assumptions.
- Vague words are replaced by examples, thresholds, commands, screenshots, API shapes, or expected states.

## Output Format

When clarification is complete, output this concise contract:

```markdown
## Acceptance Contract

Goal:
- ...

Scope:
- ...

Out of scope:
- ...

Requirements / acceptance criteria:
- ...

Done when:
- ...

Not done if:
- ...

Required verification:
- Blackbox/runtime: ...
- Tests or supporting checks: ...

Blockers / dependencies:
- ...

Accepted assumptions:
- ...
```

For implementation-agent handoff or issue creation, keep the contract strong enough that an agent can start without policy clarification: scope, out-of-scope, done-when, not-done-if, blockers, and required blackbox/runtime verification must all be present.
