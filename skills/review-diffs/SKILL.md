---
name: review-diffs
description: "Review git diffs against requirements and reachable risks; supports focused review and independent managed CLI reviews."
allowed-tools: Bash(tmux:*), Bash(git:*), Bash(mkdir:*), Bash(gh:*), Bash(rg:*), Bash(sed:*), Bash(flutter:*), Bash(npx:*), Read
---

# Review diffs

Review the requested revision against its intended behavior. Findings need a reachable trigger, concrete impact, and source evidence. Respect the caller's scope, accepted deferrals, execution backend, and required output format.

## Choose the review mode

- **Focused:** For a small, low-risk diff or an explicitly bounded re-review, inspect it in the current session. Cover requirements, correctness, and relevant security boundaries without launching reviewers or generating a review directory unless requested.
- **Managed:** Use when the caller or repository requires independent/manager-led review, or the change has substantial cross-layer behavior, security boundaries, migrations, or concurrency risk. Read [references/managed-review.md](references/managed-review.md). Its default floor is `requirements`, `correctness`, and `security`; optional specialists require concrete evidence and are capped at two.
- **Non-interactive supervisor:** When explicitly selected, read the managed procedure for the shared contract/lenses and [references/non-interactive.md](references/non-interactive.md) for execution and result delivery. Keep the three-lens floor and the supervisor's protocol. Do not use focused mode to bypass it.

Choose once and state the mode briefly. A failed managed run must remain visibly incomplete; never downgrade it to focused to claim success. Preserve an explicitly requested model/effort. Existing managed defaults remain Sol low for requirements and the configured per-lens settings; a newer model release alone is not a reason to replace them.

## Scope and evidence

Resolve the review range from the request and repository state. Include staged, unstaged, or new files only when they are part of that target. Read the linked issue when supplied; otherwise derive the contract from the request and diff. Ask only if ambiguity would change what is reviewed.

Read surrounding source and relevant callers to validate candidate findings. Separate:

- defects that violate the agreed behavior or cause concrete harm under supported conditions;
- optional cleanup or hardening that does not block the requested outcome;
- verification gaps that remain unobserved.

A hypothetical edge case, generic DRY preference, or reviewer consensus alone does not establish a blocker. Security findings may concern uncommon but reachable conditions; assess impact and the actual trust boundary, not frequency alone.

## Verification ownership

Use existing evidence when it covers the reviewed revision and affected behavior. Run additional checks for a concrete gap or a required acceptance condition. In managed mode, identify one owner for runtime/full-suite checks and give the evidence to all reviewers; specialists should not independently rerun the same suite.

Required runtime or screenshot evidence cannot be replaced by source inspection. Distinguish pass, failure, and unavailable checks. Do not weaken accepted baselines or silently waive a required check because the environment is unavailable.

## Finish the requested review

Validate and deduplicate findings, explain the smallest in-scope fix, and deliver the required report or structured result before reporting completion. Review requests alone do not authorize implementation.

For an authorized fix loop, track accepted findings and their closure conditions. Re-review the fixes and affected behavior, retaining still-valid evidence from the prior revision. Reopen settled questions only when the patch introduces a regression or new evidence invalidates the previous conclusion. A required full review remains required.

Finish when accepted blockers are resolved and required evidence is present; optional cleanup does not prolong the loop. If the same blocker repeats without progress or a fix needs new product/architecture scope, report the unresolved decision instead of repeatedly resetting a budget or expanding the implementation.

## Standard review format

```markdown
# {Category} Review

## Summary

{1-2 sentence overall assessment}

## Findings

### 1. {title}

- **Severity**: Critical / High / Medium / Low
- **Location**: `{file_path}:{line_number}`
- **Description**: {what is wrong and why}
- **Evidence**: {optional — screenshot / golden-failure image path for UI findings}
- **Suggestion**: {how to fix}
```

If there are no findings:

```markdown
# {Category} Review

No issues found.
```
