#!/usr/bin/env python3
"""CLI to durably record an opened PR in ``agent_runs``.

After the PM (or any automation) opens a PR for an issue, the ``agent_runs``
row must be advanced to ``phase = 'pr_open'`` with ``pr_number`` set so the PR
watcher picks it up. The PM runs this from its tmux pane instead of relying on
prompt memory. PM panes normally run the rendered command from
``u_agents/prompts/pm.md`` so the package root and psycopg-enabled Python
interpreter are explicit:

    PYTHONPATH=/path/to/dotfiles /path/to/python -m u_agents.mark_pr_open --repo owner/name --issue 233 --pr 240

Live runs require ``U_AGENTS_DATABASE_URL``, ``U_AGENTS_RUNNER_ID``,
``U_AGENTS_MACHINE_ID``, ``psycopg``, and reachable Postgres (same runtime as
the launcher/watchdog). ``--help`` does not import psycopg.
"""
from __future__ import annotations

import argparse
import sys

from u_agents.agent_runs import AgentRun, AgentRunsClient
from u_agents.slack_notify import notify_pr_open


def record_pr_open(
    db_client,
    repository_full_name: str,
    github_issue_number: int,
    pr_number: int,
) -> AgentRun:
    """Persist the PR-open transition via the shared client method.

    Kept separate from ``main`` so it can be unit-tested with a fake client
    without touching ``AgentRunsClient.from_env`` / psycopg.
    """
    return db_client.mark_pr_open(
        repository_full_name,
        github_issue_number,
        pr_number=pr_number,
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Record an opened PR in agent_runs (phase=pr_open, pr_number set) "
            "so the PR watcher can take over."
        )
    )
    p.add_argument("--repo", required=True, help="GitHub repository owner/name")
    p.add_argument("--issue", required=True, type=int, help="GitHub issue number")
    p.add_argument("--pr", required=True, type=int, help="opened PR number")
    args = p.parse_args(argv)

    db_client = AgentRunsClient.from_env()
    try:
        run = record_pr_open(db_client, args.repo, args.issue, args.pr)
        # Best-effort Slack notification, only after the DB transition above has
        # committed. No-op when U_AGENTS_SLACK_WEBHOOK_URL is unset; a delivery
        # failure warns but never fails the CLI or the PR-watcher hand-off.
        notify_pr_open(db_client, run)
    finally:
        db_client.close()
    print(
        f"{run.repository_full_name}#{run.github_issue_number}: "
        f"phase={run.phase} pr={run.pr_number}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
