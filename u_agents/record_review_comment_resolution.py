#!/usr/bin/env python3
"""CLI for the PM to persist a PR review comment resolution in ``review_comments``.

After the PR watcher hands a review comment to the PM, the PM validates it,
optionally fixes it, and must record the outcome durably **before** re-arming the
watcher with ``u_agents.mark_pr_open``. Writing a verdict only into a GitHub
comment is not durable state: the watcher reads ``review_comments`` (not GitHub
comment bodies), so an unrecorded resolution makes the watcher re-block the run
on the same handed-off comment.

Each comment is identified by its stable ``comment_key`` (``id:body-hash``), the
same key the watcher hand-off prompt lists. Example (run from the issue
worktree, where ``u_agents`` is not on the path and ``python3`` may lack
psycopg):

    PYTHONPATH=/path/to/dotfiles /path/to/python -m u_agents.record_review_comment_resolution \\
        --repo owner/name --issue 32 --comment-key 3409641728:1cf66a90f911 \\
        --resolution-status addressed --pm-decision valid_must_fix \\
        --commit-sha b6cd1ad --verification-summary "guarded with context.mounted; flutter test green"

Rules enforced here (and again by the DB):

- ``addressed`` requires ``--commit-sha`` and ``--verification-summary``.
- ``rejected`` / ``needs_user_judgment`` require ``--verification-summary`` as
  the reason for not fixing.

Live runs require ``U_AGENTS_DATABASE_URL``, ``U_AGENTS_RUNNER_ID``,
``U_AGENTS_MACHINE_ID``, ``psycopg``, and reachable Postgres. ``--help`` does not
import psycopg.
"""
from __future__ import annotations

import argparse
import sys

from u_agents.agent_runs import (
    AgentRunsClient,
    ReviewCommentRecord,
    validate_pm_decision,
    validate_review_comment_resolution,
    validate_verification_refs,
)
from u_agents.control_plane import (
    REVIEW_COMMENT_RESOLUTION_STATUSES,
    REVIEW_COMMENT_VERDICTS,
)


def record_resolution(
    db_client,
    repository_full_name: str,
    github_issue_number: int,
    comment_key: str,
    *,
    resolution_status: str,
    pm_decision: str | None = None,
    addressed_by_commit_sha: str | None = None,
    verification_summary: str | None = None,
    verification_refs=None,
) -> ReviewCommentRecord:
    """Persist the resolution via the shared client method.

    Kept separate from ``main`` so it can be unit-tested with a fake client
    without touching ``AgentRunsClient.from_env`` / psycopg.
    """
    return db_client.record_review_comment_resolution(
        repository_full_name,
        github_issue_number,
        comment_key,
        resolution_status=resolution_status,
        pm_decision=pm_decision,
        addressed_by_commit_sha=addressed_by_commit_sha,
        verification_summary=verification_summary,
        verification_refs=verification_refs,
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description=(
            "Record a PR review comment resolution in review_comments so the "
            "PR watcher stops re-blocking on a handed-off comment."
        )
    )
    p.add_argument("--repo", required=True, help="GitHub repository owner/name")
    p.add_argument("--issue", required=True, type=int, help="GitHub issue number")
    p.add_argument(
        "--comment-key",
        required=True,
        help="Stable comment identity (github_comment_id:body_hash)",
    )
    p.add_argument(
        "--resolution-status",
        required=True,
        choices=list(REVIEW_COMMENT_RESOLUTION_STATUSES),
        help="Durable PM resolution status",
    )
    p.add_argument(
        "--pm-decision",
        choices=list(REVIEW_COMMENT_VERDICTS),
        help="PM verdict about the comment (optional)",
    )
    p.add_argument(
        "--commit-sha",
        dest="commit_sha",
        help="Commit sha that addressed the comment (required for 'addressed')",
    )
    p.add_argument(
        "--verification-summary",
        dest="verification_summary",
        help=(
            "Short verification/justification summary (required for "
            "'addressed', and as the reason for 'rejected'/'needs_user_judgment')"
        ),
    )
    p.add_argument(
        "--verification-ref",
        dest="verification_refs",
        action="append",
        default=None,
        help="Durable evidence pointer (URL/path); repeatable",
    )
    args = p.parse_args(argv)

    # Validate cross-field rules before opening a DB connection so an invalid
    # request fails fast with a clear CLI error (exit 2), not a DB round-trip.
    try:
        validate_pm_decision(args.pm_decision)
        validate_verification_refs(args.verification_refs)
        validate_review_comment_resolution(
            args.resolution_status,
            addressed_by_commit_sha=args.commit_sha,
            verification_summary=args.verification_summary,
        )
    except ValueError as e:
        p.error(str(e))

    db_client = AgentRunsClient.from_env()
    try:
        record = record_resolution(
            db_client,
            args.repo,
            args.issue,
            args.comment_key,
            resolution_status=args.resolution_status,
            pm_decision=args.pm_decision,
            addressed_by_commit_sha=args.commit_sha,
            verification_summary=args.verification_summary,
            verification_refs=args.verification_refs,
        )
    finally:
        db_client.close()
    print(
        f"{args.repo}#{args.issue}: review comment {record.comment_key} "
        f"resolution_status={record.resolution_status} "
        f"pm_decision={record.pm_decision}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
