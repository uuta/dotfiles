# u_agents

Local DB-backed agent runner. These instructions apply only inside
`u_agents/` and its workflow docs.

## State Model

- PostgreSQL `agent_runs` is the durable coordination source for claimed work.
  GitHub issues remain the queue and implementation-contract source.
- Only the launcher creates or upserts the initial `agent_runs` row. PM,
  engineer, and reviewer agents must not create the initial row.
- Before acting on a row, verify external reality from GitHub, tmux, git
  worktrees/branches, and `tmp/review-result.json`. Do not trust DB state alone.
- Use `agent_runs.status` only for the existing coarse workflow states:
  `claimed`, `pm_started`, `engineering`, `reviewing`, `fixing`, `pr_open`,
  `pr_watching`, `ready_to_merge`, `blocked`, `done`, `cancelled`.
- Do not use `agent_runs.status` for issue-internal implementation checkpoints.
  If a coarse issue has internal phase gates, the PM creates all `run_phases`
  rows once before implementation starts. Do not add phases mid-run in the
  initial workflow.
- Store compact phase progress and evidence pointers in `run_phases.metadata`;
  keep long logs and full evidence in issue/PR comments, CI logs, or
  `tmp/review-result.json`.
- Do not invent a parallel Markdown/YAML state file for phase progress.

## Issue Granularity

- Prefer coarse, agent-ready implementation issues when the issue contract is
  strong enough: scope, out-of-scope, done-when, not-done-if, blockers, and
  required blackbox/runtime verification.
- Treat issue-internal phases as review/checkpoint gates, not automatically as
  separate GitHub sub-issues.
- Do not create implementation issues whose main purpose is policy
  clarification, specification reconciliation, or deciding what to do. Fix the
  parent issue contract first.

## Evidence

- Store short status and pointers in `metadata`; do not store long command
  output, screenshots, or full review bodies there.
- `tmp/review-result.json` remains the local reviewer handoff file and must use
  the existing status contract: `running`, `clean`, `fix_required`, or
  `blocked`.
