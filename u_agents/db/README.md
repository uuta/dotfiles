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

## Python runtime dependency

The runtime DB client imports `psycopg` only when opening a real database
connection. Unit tests and `--help` paths do not require it. Install it in the
Python environment that runs launchd/mise tasks before using the live DB-backed
launcher, watchdog, or PR watcher:

```sh
python3 -m pip install 'psycopg[binary]'
```

## Required runner configuration

Runners must read these values from configuration or environment. Agents must
not invent placeholder identities.

| Name | Meaning | Validation |
| ---- | ------- | ---------- |
| `U_AGENTS_DATABASE_URL` | PostgreSQL connection URL. | Required, non-empty, `postgresql://` or `postgres://`. |
| `U_AGENTS_RUNNER_ID` | Stable runner process/service identity. | Required, non-empty, not a placeholder such as `runner`, `placeholder`, `changeme`, or `todo`. |
| `U_AGENTS_MACHINE_ID` | Stable machine/host identity. | Required, non-empty, not a placeholder such as `machine`, `placeholder`, `changeme`, or `example`. |

## Table: agent_runs

| Column | Type | Writer | Meaning |
| ------ | ---- | ------ | ------- |
| `run_id` | `uuid` | DB default | Primary key for this claimed run. |
| `repository_full_name` | `text` | Launcher | GitHub `owner/name`. |
| `github_issue_number` | `integer` | Launcher | Claimed issue number. Must be positive. |
| `parent_branch` | `text` | Launcher | Base branch for the PR, stored separately from `branch_name`. Must be non-empty and contain no whitespace. |
| `branch_name` | `text` | Launcher | Working branch, normally `feat/<issue-number>`. Must be non-empty and contain no whitespace. |
| `status` | `text` | Runner/PM | Current run lifecycle status. See status contract below. |
| `runner_id` | `text` | Runner | Configured runner identity that claimed or owns the row. |
| `machine_id` | `text` | Runner | Configured machine identity for the row owner. |
| `locked_by` | `text` | Runner | Current lease holder identity, usually `${runner_id}@${machine_id}`. Must be set and cleared together with `lease_until`. |
| `lease_until` | `timestamptz` | Runner | Lease expiry. Must be set and cleared together with `locked_by`. Expired leases can be reclaimed after external checks. |
| `worktree_basename` | `text` | Launcher | Basename-only worktree directory, normally issue number as text. Must be non-empty, not `.` or `..`, contain no slash/backslash, and contain no whitespace. |
| `tmux_window` | `text` | Launcher/PM | Deterministic tmux window name. |
| `pm_pane` | `text` | Launcher/PM | PM pane target once known. |
| `review_result_relative_path` | `text` | Launcher/PM | Portable review JSON path inside the issue worktree. Must be `tmp/review-result.json`; each machine derives the absolute local path from its worktree root at runtime. |
| `pr_number` | `integer` | PM/runner | PR number after PR creation. Must be positive when set and is required for `pr_open`, `pr_watching`, and `ready_to_merge`. |
| `pr_review_fix_rounds` | `integer` | PR watcher | Number of automated PR review fix loops used. Defaults to `0`. |
| `block_reason` | `text` | Runner/PM | Required when `status = 'blocked'`. |
| `metadata` | `jsonb` | Runner/PM | Small structured observations. Must be a JSON object. |
| `created_at` | `timestamptz` | DB default | Row creation time. |
| `updated_at` | `timestamptz` | DB trigger | Last row update time. |

`repository_full_name` and `github_issue_number` are unique together.

## Issue-internal phase gates

`agent_runs.status` is the coarse runner workflow state. Do not add ad hoc
status values for implementation checkpoints, and do not create a parallel
Markdown/YAML state file for them.

When a coarse issue has internal phase gates, PM creates all rows in
`run_phases` once before implementation starts. Do not add new phases mid-run
for the first version of this workflow.

## Table: run_phases

| Column | Type | Writer | Meaning |
| ------ | ---- | ------ | ------- |
| `run_phase_id` | `uuid` | DB default | Primary key for this phase gate row. |
| `agent_run_id` | `uuid` | PM | Parent `agent_runs.run_id`; cascades on parent delete. |
| `phase_index` | `integer` | PM | 1-based phase order inside this run. Unique per run. |
| `phase_key` | `text` | PM | Stable machine-readable key for the phase. Unique per run. |
| `title` | `text` | PM | Human-readable phase title from the issue contract. |
| `status` | `text` | PM/runner | Phase gate status. Only one active phase per run may be `in_progress`, `reviewing`, or `fixing`. |
| `metadata` | `jsonb` | PM/runner | Short summaries and pointers to evidence. Must be a JSON object. |
| `block_reason` | `text` | PM/runner | Required when `status = 'blocked'`. |
| `created_at` | `timestamptz` | DB default | Row creation time. |
| `updated_at` | `timestamptz` | DB trigger | Last row update time. |

Allowed `run_phases.status` values are:

- `pending`
- `in_progress`
- `reviewing`
- `fixing`
- `passed`
- `blocked`
- `cancelled`

Blackbox/runtime verification evidence should be stored as a short summary and
a durable reference, for example issue/PR comments, CI logs, or
`tmp/review-result.json`. Long command output, screenshots, and full review
bodies belong outside the DB.

## Table: review_comments

PR review comment workflow state is a normalized table, not
`metadata.pr_review_comments`. JSONB shallow merges from multiple writers
corrupt shared top-level keys, and DB constraints (e.g. "addressed requires a
commit and a verification summary") cannot be enforced on free-form JSON. The
watcher records what it observed (`watcher_verdict`); the PM records the durable
resolution (`pm_decision`, `resolution_status`, commit, verification). A verdict
written only into a GitHub PR/issue comment is NOT durable state and is ignored
by the watcher.

| Column | Type | Writer | Meaning |
| ------ | ---- | ------ | ------- |
| `agent_run_id` | `uuid` | watcher | Parent `agent_runs.run_id`; cascades on parent delete. |
| `github_comment_id` | `int8` | watcher | GitHub review comment id (a derived stable id for synthetic top-level/review signals). |
| `body_hash` | `text` | watcher | Hash of the comment body; a changed body yields a new identity. |
| `comment_key` | `text` | DB generated | `github_comment_id:body_hash`, the stable identity used by the watcher, the hand-off prompt, and the PM CLI. |
| `pr_number` | `int4` | watcher | PR the comment belongs to. Must be positive. |
| `source` | `text` | watcher | `top_level`, `review_body`, `inline_review`, or `unknown`. |
| `watcher_verdict` | `text` | watcher | `valid_must_fix`, `valid_optional`, `invalid`, or `needs_user_judgment`. |
| `pm_decision` | `text` | PM | Optional PM verdict; same value set as `watcher_verdict`. |
| `resolution_status` | `text` | PM | `unresolved` (initial), `addressed`, `rejected`, or `needs_user_judgment`. |
| `handed_off_at` | `timestamptz` | watcher | Set the first time the comment is handed to the PM. |
| `resolved_at` | `timestamptz` | PM | Set for any non-`unresolved` status; null while `unresolved`. |
| `addressed_by_commit_sha` | `text` | PM | Required when `resolution_status = 'addressed'`. |
| `verification_summary` | `text` | PM | Required for `addressed`, and as the reason for `rejected`/`needs_user_judgment`. |
| `verification_refs` | `jsonb` | PM | JSON array of durable evidence pointers. |
| `first_seen_at` / `last_seen_at` | `timestamptz` | watcher | First and most recent observation of the comment. |
| `created_at` / `updated_at` | `timestamptz` | DB default/trigger | Row create / last update time. |

`(agent_run_id, comment_key)` is the primary key. The DB enforces that
`addressed` rows have both a non-empty `addressed_by_commit_sha` and a non-empty
`verification_summary`, that `resolved_at` is null exactly when `resolution_status`
is `unresolved`, and that `verification_refs` is a JSON array.

### State ownership

- watcher: detects GitHub review comments, upserts each into `review_comments`
  with its `watcher_verdict`, stamps `handed_off_at` on first hand-off, and
  decides the run's `ready_to_merge` / `blocked` / `fixing` status.
- PM: validates handed-off comments, records `pm_decision`, and sets
  `resolution_status` — `addressed` with the commit sha and verification
  summary when fixed, `rejected` with a reason, or `needs_user_judgment` only
  when a human must decide. The PM records the resolution **before** re-arming
  the watcher.
- `mark_pr_open`: only re-arms the PR watcher. It must not write any review
  comment resolution.

### PM CLI

The PM records a resolution from the issue worktree (explicit `PYTHONPATH` and a
psycopg-enabled interpreter, like `mark_pr_open`):

```sh
PYTHONPATH=/path/to/dotfiles /path/to/python -m u_agents.record_review_comment_resolution \
    --repo owner/name --issue 32 --comment-key 3409641728:1cf66a90f911 \
    --resolution-status addressed --pm-decision valid_must_fix \
    --commit-sha b6cd1ad --verification-summary "guarded with context.mounted; flutter test green"
```

### Watcher decision contract

On each pass the watcher upserts every detected comment, re-reads the table, and
decides per comment from `resolution_status` (and `watcher_verdict` /
`handed_off_at`):

- `resolution_status = 'addressed'` does not block.
- `resolution_status = 'rejected'` does not block.
- `resolution_status = 'needs_user_judgment'` blocks (a human must decide).
- `resolution_status = 'unresolved'` and `handed_off_at IS NULL` is handed off
  to the PM.
- `resolution_status = 'unresolved'` and `handed_off_at IS NOT NULL` blocks (the
  PM was asked but recorded no resolution before re-arming).
- a `watcher_verdict = 'valid_must_fix'` that is still `unresolved` follows the
  existing `pr_review_fix_rounds` budget: one auto-fix round, then `blocked`.

`valid_optional` / `invalid` comments are non-actionable and never block. The
upsert preserves the PM-owned resolution columns across passes, so an addressed
or rejected comment is never reset to `unresolved` by a later watcher
observation — this is what lets a re-armed PR reach `ready_to_merge` instead of
re-blocking on an already-handled comment.

## Status contract

Allowed `agent_runs.status` values are:

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

| Status | Meaning | Writer | Verify before acting | Next action |
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

Automated PR review comment fixes are allowed at most once, and only after a
comment has been validated.

1. If the PR is merged, set `status = 'done'`.
2. If there is a fresh validated must-fix comment (`watcher_verdict =
   'valid_must_fix'`, still `resolution_status = 'unresolved'`) and
   `pr_review_fix_rounds = 0`, set `status = 'fixing'`, increment
   `pr_review_fix_rounds`, and assign the engineer the must-fix list.
3. If such a must-fix comment is still `unresolved` after the one allowed round,
   set `status = 'blocked'` (it cannot be auto-fixed again and must not be
   ignored).
4. If any comment needs a human decision:
   - a fresh `needs_user_judgment` comment (`handed_off_at IS NULL`) is handed to
     the existing PM pane for validation and parked in `status = 'fixing'` until
     the PM records a resolution in `review_comments` and re-arms the watcher
     with `mark_pr_open`;
   - a comment the PM escalated (`resolution_status = 'needs_user_judgment'`), or
     one handed off but re-armed with no recorded resolution (`unresolved` and
     `handed_off_at IS NOT NULL`), sets `status = 'blocked'` so a human decides
     (no repeat auto-handoff). With no live dispatcher, a fresh
     `needs_user_judgment` comment also blocks.
5. If there is a fresh validated must-fix comment and
   `pr_review_fix_rounds >= 1`, set `status = 'blocked'` (global round cap).
6. If CI is green and there are no actionable/unresolved/judgment comments, set
   `status = 'ready_to_merge'`.
7. Otherwise remain in `status = 'pr_watching'`.

The watcher collects both top-level PR comments / review summaries and inline
review comments (`/repos/{owner}/{repo}/pulls/{n}/comments`). If the inline
fetch fails or returns malformed output, the pass is deferred (transient), not
treated as "no comments". Comments are not always correct, so **every**
candidate — inline comments, top-level comments with a must-fix or
forward-action signal, `CHANGES_REQUESTED` review summaries, and a bare
`reviewDecision = CHANGES_REQUESTED` — passes through the validation gate before
it can become a must-fix input; none auto-trigger a fix. Verdicts are
`valid_must_fix`,
`valid_optional`, `invalid`, and `needs_user_judgment`. Marker text, a
`CHANGES_REQUESTED` summary, high-priority styling, or bot authorship alone
never make a comment `valid_must_fix`.

The default stance is to validate and address, not to skip. The runtime
`default_validate_comment` classifier drops a comment without PM review only
when it is clearly obsolete/dismissed (`invalid`) or explicitly optional/empty
(`valid_optional`); any other comment with a body — including a plain inline
comment with no marker text — is escalated to `needs_user_judgment` so it
reaches the PM validation gate instead of being silently treated as optional.
At that gate the PM (or another injected validator) must address a comment
unless it is clearly invalid:

- `invalid` only when the comment is factually wrong, contradicts the
  issue/spec, would break behavior, is already obsolete, or is impossible to
  apply with a concrete reason.
- `valid_optional` is rare: only explicitly optional/non-blocking/nit comments,
  or purely cosmetic comments out of the current scope.
- `needs_user_judgment` only for product/spec decisions, scope changes, or
  ambiguous tradeoffs the implementation agent cannot decide.
- When unsure between `valid_must_fix` and `valid_optional`, choose
  `valid_must_fix`. Not being fully certain is not a reason to skip a comment.

### Per-comment durable state

Per-comment state lives in the `review_comments` table (see above), keyed by
`comment_key` (`github_comment_id:body_hash`), not in `metadata.pr_review_comments`.
The watcher upserts each detected comment every pass, preserving the PM-owned
resolution columns, so prior `resolution_status` / `handed_off_at` state is never
lost when a fetch returns fewer/no comments. A `valid_must_fix` comment triggers
one automated fix round (capped globally by `pr_review_fix_rounds`); if it is
still `unresolved` afterward it escalates to `blocked` rather than being ignored.
A `needs_user_judgment` comment is handed off to the PM pane at most once
(`handed_off_at`); after the PM re-arms the watcher with `mark_pr_open`, the same
still-`unresolved` key blocks instead of being re-sent. A changed body yields a
new `comment_key`, so an edited comment is treated as a fresh validation
candidate. `metadata.pr_review_comments` is no longer the source of truth; the
watcher reads the table, and the PM CLI (not a GitHub comment body) is how a
resolution becomes durable.

The PR watcher never merges a PR. `ready_to_merge` is a notification state for
the user/operator after GitHub PR existence, head branch, CI, and validated
comment state have been verified.
