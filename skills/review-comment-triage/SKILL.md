---
name: review-comment-triage
description: Triage GitHub PR review comments after a PR is open and decide whether each comment is worth fixing, should be rejected, is optional cleanup, or needs user/product judgment. Use when the user asks if a PR review comment is valid, worth fixing, should be addressed, or asks to inspect GitHub review feedback without immediately changing code.
allowed-tools: Bash(gh:*), Bash(git:*), Bash(rg:*), Bash(sed:*)
---

# Review Comment Triage

## Goal

Decide whether GitHub PR review feedback should enter a fix loop.

This skill is for **after a PR exists**. It is not a replacement for
`review-diffs`, which reviews local diffs before PR creation.

## Core Rule

Do not implement changes during triage unless the user explicitly asks to fix
after the classification. The default output is judgment plus reasoning.

## Classification

Classify each actionable review thread as exactly one:

- `must_fix`: Real correctness, security, data-loss, merge-blocking, or contract-violating issue.
- `should_fix`: Real issue or clear maintainability problem with low-risk patch, but not merge-blocking.
- `optional_cleanup`: Technically valid cleanup, style, simplification, or minor test hygiene with little product/runtime value.
- `reject`: Not worth fixing because it conflicts with the issue contract, weakens a tested boundary, is already covered, is out of scope, or creates more risk than value.
- `needs_user_decision`: Multiple valid choices exist and the decision changes product behavior, API contract, UX, or scope.

## Workflow

1. Resolve the PR and review thread.
   - If the user provides a PR URL or review URL, use it directly.
   - Prefer `gh api graphql` for thread-aware data: `isResolved`, `isOutdated`, file path, line, diff hunk, and all comments.
   - Use `gh pr view --json reviews,comments,reviewDecision,mergeStateStatus,statusCheckRollup` for PR-level context.
2. Read enough context to judge the comment.
   - Review thread body and diff hunk.
   - Current file around the commented line.
   - Relevant tests.
   - Linked issue or sub-issue contract when available.
   - Existing project conventions if the comment is about style/logging/test structure.
3. Determine whether the suggestion preserves or weakens the contract.
   - Treat tested boundary contracts as strong evidence.
   - A comment can be technically true and still be `reject` if it weakens a deliberate guardrail.
   - A comment can be low-risk but still only `optional_cleanup` if it does not improve behavior.
4. Summarize the decision.
   - Findings / classifications first.
   - Explain tradeoff briefly.
   - If `must_fix` or `should_fix`, describe the smallest safe patch and verification.
   - If `reject`, provide a concise PR reply draft.
   - If `needs_user_decision`, ask the exact decision question.

## Decision Heuristics

Prefer `must_fix` when:

- The comment identifies a currently reachable bug.
- The PR fails its issue/sub-issue `Done when` criteria.
- The suggestion prevents auth/session, payment, data integrity, security, or release failure.
- CI is green only because the missing case is not tested.

Prefer `should_fix` when:

- The comment is correct and the patch is small, safe, and aligned with the issue contract.
- The current code is misleading enough to likely cause future bugs.
- The change removes dead code without weakening a boundary contract.

Prefer `optional_cleanup` when:

- The comment is correct but cosmetic or hygiene-only.
- The patch has negligible runtime/product value.
- Leaving it does not confuse the contract or future maintenance.

Prefer `reject` when:

- The suggestion conflicts with the issue contract or accepted deferrals.
- The suggestion removes defensive code that protects a documented/tested boundary.
- The comment assumes a different scope than the PR.
- The fix would broaden the PR into unrelated work.
- The review is stale, outdated, duplicated, or already addressed.

Prefer `needs_user_decision` when:

- The right answer depends on product policy or UX.
- The fix changes public API, persistence, routing, auth semantics, billing behavior, or compatibility.
- There are two reasonable implementations with different tradeoffs.

## Output Format

Use this format by default:

```markdown
## Triage

- `classification`: comment summary
  - Worth fixing: yes/no/optional
  - Reason: ...
  - Suggested action: ...

## PR Reply Draft

...

## Verification If Fixed

- ...
```

If multiple comments exist, group by thread and order by severity:
`must_fix`, `needs_user_decision`, `should_fix`, `optional_cleanup`, `reject`.

## GitHub Writes

- Do not reply to GitHub comments unless the user explicitly asks.
- Do not resolve threads unless the user explicitly asks.
- If asked to reply, keep the response short and factual.

## Relationship To Other Skills

- Use `review-diffs` before PR creation to review local diffs.
- Use this skill after PR creation to decide whether review comments deserve code changes.
- If a comment is classified `must_fix` or `should_fix` and the user asks to fix it, use the normal implementation/review loop afterward.
