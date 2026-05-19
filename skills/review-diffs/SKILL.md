---
name: review-diffs
description: Review git diffs with a manager-led workflow that preserves issue requirements. First derive a shared review contract from the user request and any linked issue or PR, then run several tmux review agents in parallel with different lenses, and finally perform a manager pass that checks total requirement coverage before summarizing.
allowed-tools: Bash(tmux:*), Bash(git:*), Bash(mkdir:*), Bash(gh:*), Bash(rg:*), Bash(sed:*)
---

# Review diffs

## Goal

Use parallel reviewers to find problems in a diff without losing issue-level direction.

If the user wants this review to be part of a repeated `watch -> review -> fix -> repeat` supervisor loop around Claude Code in tmux, use `claude-tmux-review-loop`. This skill is the review dependency inside that larger loop.

The manager owns:

- review scope
- issue / PR requirement coverage
- accepted deferrals and out-of-scope boundaries
- final judgment

The tmux reviewers are specialists. They do not decide the total direction on their own.

## Workflow

1. Build a review contract before spawning reviewers
2. Capture the diff to a temp file
3. Create `docs/review/`
4. Launch parallel tmux reviewers
5. Give every reviewer the same contract plus one role-specific lens
6. Poll until all reviewers finish
7. Perform a manager pass against the contract and the diff
8. Summarize findings to the user
9. Clean up review windows

## 1. Build the review contract

Before opening tmux reviewers, read enough context to define what “correct” means.

Preferred sources, in order:

- the user request
- linked GitHub issue / PR / review comments
- parent issue if the task is a sub-issue
- the current diff and touched files

If the user supplied an issue or PR number, read it. If the branch or commit message clearly references one, read that too. If there is no explicit issue, infer the contract from the request and changed files.

Write a short contract to `docs/review/contract.md` with:

- change goal
- canonical behavior after the change
- old behavior handling
- in-scope files / layers
- explicit out-of-scope boundaries
- accepted deferrals or known caveats
- review range being inspected
- visual contract / approved reference image / golden or screenshot baseline rules when the diff is screenshot-driven UI

Example skeleton:

```markdown
# Review Contract

- Goal: replace Auth0-based purchase identity with RevenueCat identity keyed by Supabase session.user.id.
- Canonical behavior: purchase login and entitlement checks must use the new auth core and expose CustomerInfo-derived state for routing.
- Old behavior handling: Auth0 `sub` and restore-as-startup-check must not remain in the main flow.
- In scope: purchase service, purchase state/notifier, purchase page, settings entry points, index bootstrap.
- Out of scope: onboarding orchestration, API upsert flow, unrelated UI cleanup.
- Accepted deferrals: stale generated lockfiles blocked by unrelated tooling issues may be noted but are not blockers.
- Review range: current worktree diff against origin/master.
```

This step is mandatory. Do not spawn reviewers before the contract exists.

The contract must live inside the current worktree so review state stays issue-scoped and inspectable later.

If the issue includes screenshot/mockup/ideal-image visual requirements, the contract must also state:

- the approved visual source
- the visual invariants being protected
- whether a visual shell / draft UI task should already exist
- which golden/screenshot/component visual tests are binding
- that baselines, thresholds, selectors, and visual expectations may not be changed without user approval
- what screenshot/golden evidence is required for review clean

## 2. Capture the diff

```bash
git diff > docs/review/diff.txt
```

If the diff is empty, try a more explicit range such as:

```bash
git diff origin/main...
git diff HEAD~1
```

If the range is still ambiguous, stop and clarify the review target before continuing.

## 3. Prepare the output directory

```bash
mkdir -p docs/review
```

Recommended output files:

- `docs/review/requirements.md`
- `docs/review/correctness.md`
- `docs/review/resilience.md`
- `docs/review/security.md`
- `docs/review/reuse.md`
- `docs/review/manager.md`

## 4. Launch parallel tmux reviewers

Create dedicated tmux windows. Each runs Claude Code with `--dangerously-skip-permissions`.

Model / effort policy:

- `review-req` uses `--model opus --effort high`. Requirement compliance needs the strongest judgment.
- The other 4 specialist reviewers use `--model sonnet --effort high`. Each has a narrow lens, so sonnet-high is the cost-efficient default for parallel work.
- The manager pass (step 7) is run serially by the current session and inherits whatever model / effort the caller is using. Prefer running the skill itself under opus / high when possible.

```bash
tmux new-window -n review-req -c "$(pwd)" 'claude --dangerously-skip-permissions --model opus --effort high'
tmux new-window -n review-correctness -c "$(pwd)" 'claude --dangerously-skip-permissions --model sonnet --effort high'
tmux new-window -n review-resilience -c "$(pwd)" 'claude --dangerously-skip-permissions --model sonnet --effort high'
tmux new-window -n review-security -c "$(pwd)" 'claude --dangerously-skip-permissions --model sonnet --effort high'
tmux new-window -n review-reuse -c "$(pwd)" 'claude --dangerously-skip-permissions --model sonnet --effort high'
```

Wait for each window to become ready by polling `tmux capture-pane` until the idle prompt appears.

## 5. Give every reviewer the same contract

Use `load-buffer` -> `paste-buffer` -> `C-m` for each window. Every prompt must include:

- `Read docs/review/contract.md first`
- `Read docs/review/diff.txt second`
- `Respect out-of-scope and accepted deferrals`
- `Do not judge overall success of the issue; only report findings from your lens`

### Agent 1: requirements

```text
Read docs/review/contract.md first, then docs/review/diff.txt.

Review only for requirement compliance and scope control.

Focus on:
- issue checklist items that are still unmet
- behavior that contradicts the canonical flow
- old behavior that should have been removed or redirected
- scope creep that solves the wrong problem
- known caveats that should be documented but are missing
- for screenshot-driven UI, missing visual evidence, weakened golden/screenshot tests, or drift from the approved visual contract

Do not spend time on generic style or speculative refactors.

Write to docs/review/requirements.md in the standard review format.
If there are no findings, say "No issues found."
```

### Agent 2: correctness (bug + integration)

```text
Read docs/review/contract.md first, then docs/review/diff.txt.

Review for correctness — both single-file bugs and cross-file integration regressions.

Single-file bugs:
- broken control flow, incorrect return values, wrong identifiers or stale state usage
- missing error handling that now breaks the intended flow
- null / type / lifecycle issues that are clearly reachable
- only report issues that are bugs now, not hypothetical ones

Cross-file integration:
- mismatches between service, notifier, and UI layers
- bootstrap / restore / routing state inconsistencies
- partial migrations that leave one side of an interface on the old model
- generated or config artifacts that now disagree with the code
- fragile assumptions across call boundaries

Write to docs/review/correctness.md in the standard review format.
If there are no findings, say "No issues found."
```

### Agent 3: resilience (failure paths + performance)

```text
Read docs/review/contract.md first, then docs/review/diff.txt.

Review for resilience — failure handling gaps and performance regressions.

Failure paths:
- async calls that can fail but are not caught or surfaced
- state that can be left inconsistent after failure
- missing cleanup, loading reset, or rollback on unhappy paths
- retries, timeouts, fallback behavior, or cancellation assumptions
- error propagation mismatches between lower layers and user-visible state

Performance:
- repeated expensive work on hot paths
- redundant network calls
- unnecessary allocations or recomputation
- blocking work introduced into startup or frequent UI flows

Treat network calls, plugin calls, subprocesses, file I/O, database access, API boundaries, and background tasks as the main risk areas.

Write to docs/review/resilience.md in the standard review format.
If there are no findings, say "No issues found."
```

### Agent 4: security

```text
Read docs/review/contract.md first, then docs/review/diff.txt.

Review for security issues introduced or exposed by the diff.

Focus on:
- auth or entitlement bypass
- trust-boundary mistakes
- secret leakage
- unsafe token handling
- injection / path / network boundary issues

Write to docs/review/security.md in the standard review format.
If there are no findings, say "No issues found."
```

### Agent 5: reuse / cohesion

```text
Read docs/review/contract.md first, then docs/review/diff.txt.

Review for comprehension debt, missed reuse, parallel implementations, responsibility drift, and unnecessary helper extraction.

Focus on:
- new helpers, functions, classes, hooks, components, validators, constants, enums, routes, errors, fixtures, or test builders that duplicate an existing responsibility
- local validation or authorization logic when a schema, guard, interceptor, decorator, domain validator, or shared helper already owns that behavior
- direct SQL, direct API calls, direct file access, or direct service calls that bypass established repository/client/service conventions
- new generic files such as `utils`, `helpers`, `common`, or `constants` when existing shared locations already exist
- new methods extracted only once with unclear responsibility or names that hide rather than remove complexity
- abstractions introduced before concrete variation exists
- code that appears to have inspected only the nearby file while ignoring adjacent patterns in the same layer

Prefer reuse, relocation, deletion, or consolidation over new abstraction.
Recommend abstraction only when there are at least two concrete implementations with the same responsibility and a stable shared concept.

Do not:
- suggest generic DRY cleanup that is unrelated to the diff's behavioral responsibility
- demand abstraction for one-off code
- report duplication unless it creates a concrete maintenance, correctness, or consistency risk
- fight the existing architecture just because a different general pattern exists

Write to docs/review/reuse.md in the standard review format.
If there are no findings, say "No issues found."
```

## 6. Poll until all reviewers finish

For each window, poll every 5 seconds:

```bash
tmux capture-pane -p -t <window> -S -50
```

A reviewer is done when:

- the output file has been written, and
- the pane is back at the idle Claude prompt

## 7. Manager pass is mandatory

After the tmux reviewers finish, do not immediately relay their output.

Perform one serial manager pass yourself:

1. Re-read `docs/review/contract.md`
2. Re-scan the diff
3. Read all reviewer outputs
4. Decide which findings are real, duplicated, or out of scope
5. Check the issue-level checklist end to end

Write the manager conclusion to `docs/review/manager.md` with:

- overall assessment
- remaining blockers
- accepted deferrals
- residual risks / test gaps

The manager pass must answer:

- Does the diff satisfy the intended issue direction?
- Is any required behavior still missing?
- Are any reviewers flagging problems that are outside the agreed scope?
- For screenshot-driven UI, did the implementation preserve the visual contract and avoid unauthorized baseline/threshold/selector changes?

## 8. Summarize to the user

Findings come first.

When responding:

- lead with real findings ordered by severity
- include file and line references
- call out requirement gaps before secondary observations
- explicitly state when no findings remain
- mention residual risks and verification gaps separately

Do not simply aggregate reviewer counts. The output should reflect the manager’s judgment.

## 9. Cleanup

Close the review windows when finished:

```bash
tmux kill-window -t review-req
tmux kill-window -t review-correctness
tmux kill-window -t review-resilience
tmux kill-window -t review-security
tmux kill-window -t review-reuse
```

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
- **Suggestion**: {how to fix}
```

If there are no findings:

```markdown
# {Category} Review

No issues found.
```
