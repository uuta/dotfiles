# u_agents v0.2 DB control plane

The v0.2 control plane coordinates claimed work across runners and machines.
GitHub Issues with `status:ready` remain the queue source of truth. The DB
stores only claimed work in `agent_runs`; it does not store queued/discovered
issues.

Only the Launcher creates or upserts the initial `agent_runs` row. PM,
engineer, and reviewer agents must not create the initial DB row.

Before any runner acts on a DB row, it must verify external reality from the
appropriate source: GitHub issue labels, GitHub PR state, tmux panes, git
worktrees/branches, and `tmp/review-result.json`.

The claim order is DB claim/lease first, then GitHub label swap. After the DB
lease is acquired, the Launcher must re-check the GitHub issue before changing
labels or starting tmux work.

## Local Postgres

`u_agents/compose.yml` runs PostgreSQL 17 on localhost port `54329`.

```sh
cd u_agents
mise run db-up
mise run db-psql
mise run db-down
```

Default local development URL:

```text
postgresql://u_agents:u_agents_dev_password@127.0.0.1:54329/u_agents
```

## Required runner configuration

Runners must read these values from configuration or environment. Agents must
not invent placeholder identities.

| Name | Meaning | Validation |
| ---- | ------- | ---------- |
| `U_AGENTS_DATABASE_URL` | PostgreSQL connection URL. | Required, non-empty. |
| `U_AGENTS_RUNNER_ID` | Stable runner process/service identity. | Required, non-empty. |
| `U_AGENTS_MACHINE_ID` | Stable machine/host identity. | Required, non-empty. |

## Table: agent_runs

| Column | Type | Writer | Meaning |
| ------ | ---- | ------ | ------- |
| `run_id` | `uuid` | DB default | Primary key for this claimed run. |
| `repository_full_name` | `text` | Launcher | GitHub `owner/name`. |
| `github_issue_number` | `integer` | Launcher | Claimed issue number. Must be positive. |
| `parent_branch` | `text` | Launcher | Base branch for the PR, stored separately from `branch_name`. Must be non-empty and contain no whitespace. |
| `branch_name` | `text` | Launcher | Working branch, normally `feat/<issue-number>`. Must be non-empty and contain no whitespace. |
| `phase` | `text` | Runner/PM | Current coordination phase. See phase contract below. |
| `runner_id` | `text` | Runner | Configured runner identity that claimed or owns the row. |
| `machine_id` | `text` | Runner | Configured machine identity for the row owner. |
| `locked_by` | `text` | Runner | Current lease holder identity, usually `${runner_id}@${machine_id}`. Must be set and cleared together with `lease_until`. |
| `lease_until` | `timestamptz` | Runner | Lease expiry. Must be set and cleared together with `locked_by`. Expired leases can be reclaimed after external checks. |
| `worktree_basename` | `text` | Launcher | Basename-only worktree directory, normally issue number as text. Must be non-empty, not `.` or `..`, contain no slash/backslash, and contain no whitespace. |
| `tmux_window` | `text` | Launcher/PM | Deterministic tmux window name. |
| `pm_pane` | `text` | Launcher/PM | PM pane target once known. |
| `engineer_pane` | `text` | PM | Engineer pane target once created. |
| `reviewer_pane` | `text` | PM | Reviewer pane target once created. |
| `review_result_relative_path` | `text` | Launcher/PM | Portable review JSON path inside the issue worktree. Must be `tmp/review-result.json`; each machine derives the absolute local path from its worktree root at runtime. |
| `pr_number` | `integer` | PM/runner | PR number after PR creation. Must be positive when set and is required for `pr_open`, `pr_watching`, and `ready_to_merge`. |
| `pr_review_fix_rounds` | `integer` | PR watcher | Number of automated PR review fix loops used. Defaults to `0`. |
| `block_reason` | `text` | Runner/PM | Required when `phase = 'blocked'`. |
| `metadata` | `jsonb` | Runner/PM | Small structured observations. Must be a JSON object. |
| `created_at` | `timestamptz` | DB default | Row creation time. |
| `updated_at` | `timestamptz` | DB trigger | Last row update time. |

`repository_full_name` and `github_issue_number` are unique together.

## Phase contract

Allowed `phase` values are:

```text
claimed
pm_started
engineering
reviewing
fixing
pr_open
pr_watching
ready_to_merge
blocked
done
cancelled
```

| Phase | Meaning | Writer | Verify before acting | Next action |
| ----- | ------- | ------ | -------------------- | ----------- |
| `claimed` | DB lease acquired for a `status:ready` issue. | Launcher | Issue still exists, is open, and has `status:ready`; no duplicate live tmux PM for this issue. | Swap GitHub label to `status:in-progress`, ensure PM tmux window, send PM prompt, then set `pm_started`. |
| `pm_started` | PM tmux pane exists and prompt was sent. | Launcher | PM pane is a live expected agent process; worktree/branch reality matches row. | PM starts workspace setup and moves to `engineering`. |
| `engineering` | Engineer is implementing in the issue worktree. | PM | Engineer pane exists; git diff/branch is for this issue; issue requirements still apply. | Wait/watch engineer. When implementation is ready, set `reviewing`. |
| `reviewing` | Local reviewer is reviewing the branch diff. | PM | Reviewer pane exists; `review_result_relative_path` is `tmp/review-result.json` and that file exists or was initialized to `running` under the local issue worktree. | Read `tmp/review-result.json`; `clean` goes to PR creation, `fix_required` goes to `fixing`, `blocked` goes to `blocked`, and still `running` after 5 minutes goes to reviewer-stall recovery. |
| `fixing` | Engineer is fixing local review or PR review must-fix items. | PM/PR watcher | Must-fix items are current and in scope; engineer pane/worktree still valid. | After fixes, return to `reviewing` for local findings or `pr_watching` for PR findings. |
| `pr_open` | PR exists but CI/review state has not been fully observed. | PM | PR number exists on GitHub and branch/head match the row. | Begin CI/review observation and set `pr_watching`. |
| `pr_watching` | Runner is watching CI plus Gemini/human review comments. | PR watcher | PR still exists; CI status and review comments are current; branch still matches row. | Apply PR watcher rules below. |
| `ready_to_merge` | CI is green and must-fix review comments are addressed, rejected, or optional. | PR watcher | Re-check PR mergeability, CI, and review comments before notifying user. | Report that the user can merge. |
| `blocked` | A user or external decision is required. | Any runner/PM | `block_reason` is specific and still accurate. | Do not auto-advance. User or external state must resolve it. |
| `done` | PR merged or issue completed. | PR watcher/runner | PR merge or issue completion is true on GitHub. | Cleanup can happen. |
| `cancelled` | Work was intentionally stopped. | User/runner | Cancellation is intentional; no runner should continue the row. | No action except cleanup. |

## PR watcher rules

Automated PR review comment fixes are allowed at most once.

1. If the PR is merged, set `phase = 'done'`.
2. If there are must-fix PR comments and `pr_review_fix_rounds = 0`, set
   `phase = 'fixing'`, increment `pr_review_fix_rounds`, and assign the
   engineer the current must-fix list.
3. If there are must-fix PR comments and `pr_review_fix_rounds >= 1`, set
   `phase = 'blocked'` with a `block_reason`.
4. If CI is green and there are no must-fix review comments, set
   `phase = 'ready_to_merge'`.
5. Otherwise remain in `phase = 'pr_watching'`.

Review comment classification must distinguish must-fix items from optional,
rejected, stale, or already-addressed comments before applying these rules.
