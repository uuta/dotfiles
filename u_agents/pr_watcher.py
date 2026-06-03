#!/usr/bin/env python3
"""DB-backed PR watcher for u_agents."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable

from u_agents.agent_runs import AgentRun, AgentRunsClient
from u_agents.control_plane import decide_pr_watch_phase


@dataclass(frozen=True)
class PrReality:
    exists: bool
    pr_number: int
    head_branch: str
    merged: bool
    ci_green: bool
    must_fix_review_comments: bool
    closed: bool = False
    must_fix_comment_keys: tuple[str, ...] = ()


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _status_checks_green(status_rollup) -> bool:
    """Whether every status-rollup entry is green.

    GitHub's ``statusCheckRollup`` mixes two GraphQL shapes:
    - ``CheckRun`` entries expose ``status`` (e.g. ``COMPLETED``) and
      ``conclusion`` (``SUCCESS``/``SKIPPED``/``NEUTRAL``/``FAILURE``/...).
    - ``StatusContext`` entries (classic commit statuses) expose ``state``
      (``SUCCESS``/``PENDING``/``FAILURE``/``ERROR``/``EXPECTED``).
    A successful classic status counts as green; pending/failing/error classic
    statuses do not.
    """
    if not isinstance(status_rollup, list) or not status_rollup:
        return False
    for check in status_rollup:
        if not isinstance(check, dict):
            return False
        if "state" in check:
            if check.get("state") != "SUCCESS":
                return False
        else:
            status = check.get("status")
            conclusion = check.get("conclusion")
            if status != "COMPLETED" or conclusion not in (
                "SUCCESS", "SKIPPED", "NEUTRAL"
            ):
                return False
    return True


_MUST_FIX_MARKERS = (
    "must_fix",
    "must-fix",
    "must fix",
    "changes requested",
    "blocking",
    "blocker",
)
_NON_MUST_FIX_MARKERS = (
    "optional",
    "non-blocking",
    "nonblocking",
    "nit:",
    "already addressed",
    "addressed",
    "resolved",
    "stale",
    "rejected",
)


def _comment_body(item) -> str:
    if not isinstance(item, dict):
        return ""
    return str(item.get("body") or "")


def _comment_key(prefix: str, item: dict, fallback_index: int) -> str:
    value = item.get("id") or item.get("databaseId") or item.get("url")
    if value:
        return f"{prefix}:{value}"
    return f"{prefix}:index-{fallback_index}"


def _body_has_must_fix_signal(body: str) -> bool:
    normalized = body.lower().replace("_", "-")
    if not any(marker in normalized for marker in _MUST_FIX_MARKERS):
        return False
    return not any(marker in normalized for marker in _NON_MUST_FIX_MARKERS)


def extract_must_fix_review_comment_keys(pr_data: dict) -> tuple[str, ...]:
    """Classify PR comments/reviews with explicit must-fix signals.

    Only ``comments`` and ``latestReviews`` (the latest review per reviewer)
    are considered. The historical ``reviews`` list is intentionally excluded
    so a superseded ``CHANGES_REQUESTED`` review that was later replaced by an
    ``APPROVED`` review does not keep a PR blocked forever.

    This is intentionally conservative and testable. Runtime callers still
    pass the resulting truth through `PrReality`, and tests can inject richer
    classification without depending on GitHub's JSON shape.
    """
    keys: list[str] = []
    for prefix, field in (
        ("comment", "comments"),
        ("latest_review", "latestReviews"),
    ):
        values = pr_data.get(field) or []
        if not isinstance(values, list):
            continue
        for index, item in enumerate(values):
            if not isinstance(item, dict):
                continue
            state = str(item.get("state") or "").upper()
            body = _comment_body(item)
            if state == "CHANGES_REQUESTED" or _body_has_must_fix_signal(body):
                keys.append(_comment_key(prefix, item, index))
    return tuple(keys)


# "could not resolve to" matches GitHub GraphQL missing-resource errors
# (e.g. "Could not resolve to a PullRequest ..."). It deliberately excludes
# transient DNS/network failures like "Could not resolve host: api.github.com".
_PR_ABSENCE_MARKERS = ("not found", "could not resolve to", "404")


def _missing_pr_reality(pr_number: int) -> PrReality:
    return PrReality(
        exists=False,
        pr_number=pr_number,
        head_branch="",
        merged=False,
        ci_green=False,
        must_fix_review_comments=False,
    )


def fetch_pr_reality(repository_full_name: str, pr_number: int) -> PrReality:
    res = _run([
        "gh", "pr", "view", str(pr_number),
        "--repo", repository_full_name,
        "--json",
        (
            "number,headRefName,state,merged,statusCheckRollup,reviewDecision,"
            "comments,latestReviews"
        ),
    ])
    if res.returncode != 0:
        stderr = (res.stderr or "").lower()
        if any(marker in stderr for marker in _PR_ABSENCE_MARKERS):
            return _missing_pr_reality(pr_number)
        # Transient network/rate-limit/outage: do not let it masquerade as a
        # definitively missing PR (which would terminally block the run).
        raise RuntimeError(
            f"gh pr view failed for {repository_full_name}#{pr_number} "
            f"(exit {res.returncode}); treating as transient: "
            f"{(res.stderr or '').strip()}"
        )
    try:
        data = json.loads(res.stdout)
    except json.JSONDecodeError as e:
        # Malformed CLI output is ambiguous, not proof the PR is gone.
        raise RuntimeError(
            f"gh pr view returned unparseable JSON for "
            f"{repository_full_name}#{pr_number}: {e}"
        ) from e
    state = data.get("state")
    must_fix_comment_keys = extract_must_fix_review_comment_keys(data)
    if not must_fix_comment_keys and data.get("reviewDecision") == "CHANGES_REQUESTED":
        must_fix_comment_keys = ("reviewDecision:CHANGES_REQUESTED",)
    return PrReality(
        exists=True,
        pr_number=int(data["number"]),
        head_branch=str(data.get("headRefName") or ""),
        merged=bool(data.get("merged")),
        closed=state == "CLOSED",
        ci_green=_status_checks_green(data.get("statusCheckRollup")),
        must_fix_review_comments=bool(must_fix_comment_keys),
        must_fix_comment_keys=must_fix_comment_keys,
    )


def reconcile_pr_run(
    run: AgentRun,
    reality: PrReality,
    db_client,
    *,
    assign_fix: Callable[[AgentRun, PrReality], None] | None = None,
) -> AgentRun:
    if run.pr_number is None:
        return db_client.mark_blocked(
            run.repository_full_name,
            run.github_issue_number,
            "PR watcher cannot verify a run without pr_number",
            metadata={"pr_watcher": {"verified": False}},
        )
    if not reality.exists:
        return db_client.mark_blocked(
            run.repository_full_name,
            run.github_issue_number,
            f"PR #{run.pr_number} does not exist on GitHub",
            metadata={"pr_watcher": {"verified": False}},
        )
    if reality.pr_number != run.pr_number:
        return db_client.mark_blocked(
            run.repository_full_name,
            run.github_issue_number,
            f"GitHub returned PR #{reality.pr_number}; expected #{run.pr_number}",
            metadata={"pr_watcher": {"verified": False}},
        )
    if reality.head_branch != run.branch_name:
        return db_client.mark_blocked(
            run.repository_full_name,
            run.github_issue_number,
            f"PR #{run.pr_number} head branch {reality.head_branch!r} "
            f"does not match {run.branch_name!r}",
            metadata={"pr_watcher": {"verified": False}},
        )
    if reality.closed and not reality.merged:
        return db_client.mark_blocked(
            run.repository_full_name,
            run.github_issue_number,
            f"PR #{run.pr_number} is closed without being merged",
            metadata={"pr_watcher": {"verified": True, "closed": True}},
        )

    decision = decide_pr_watch_phase(
        pr_merged=reality.merged,
        ci_green=reality.ci_green,
        must_fix_review_comments=reality.must_fix_review_comments,
        pr_review_fix_rounds=run.pr_review_fix_rounds,
    )
    metadata = {
        "pr_watcher": {
            "verified": True,
            "pr_number": reality.pr_number,
            "head_branch": reality.head_branch,
            "ci_green": reality.ci_green,
            "must_fix_review_comments": reality.must_fix_review_comments,
            "must_fix_review_comment_count": len(reality.must_fix_comment_keys),
            "must_fix_comment_keys": list(reality.must_fix_comment_keys[:20]),
            "merged": reality.merged,
            "closed": reality.closed,
        },
    }
    if decision.phase == "done":
        return db_client.mark_done(
            run.repository_full_name,
            run.github_issue_number,
            metadata=metadata,
        )
    if decision.phase == "blocked":
        return db_client.mark_blocked(
            run.repository_full_name,
            run.github_issue_number,
            decision.block_reason,
            metadata=metadata,
        )
    updated = db_client.update_pr_fields(
        run.repository_full_name,
        run.github_issue_number,
        pr_number=reality.pr_number,
        phase=decision.phase,
        increment_fix_rounds=decision.increment_fix_rounds,
        metadata=metadata,
    )
    if decision.increment_fix_rounds and assign_fix is not None:
        assign_fix(updated, reality)
    return updated


def check_once(
    db_client,
    *,
    fetch_reality: Callable[[str, int], PrReality] = fetch_pr_reality,
    assign_fix: Callable[[AgentRun, PrReality], None] | None = None,
) -> list[AgentRun]:
    updated: list[AgentRun] = []
    for run in db_client.list_pr_watch_runs():
        if run.pr_number is None:
            updated.append(reconcile_pr_run(
                run,
                PrReality(False, 0, "", False, False, False),
                db_client,
                assign_fix=assign_fix,
            ))
            continue
        try:
            reality = fetch_reality(run.repository_full_name, run.pr_number)
        except RuntimeError as e:
            # Transient/ambiguous fetch failure: skip this run so it is retried
            # on the next pass instead of being terminally blocked.
            print(
                f"WARN: deferring PR watch for {run.repository_full_name}#"
                f"{run.github_issue_number}: {e}",
                file=sys.stderr,
            )
            continue
        updated.append(reconcile_pr_run(
            run,
            reality,
            db_client,
            assign_fix=assign_fix,
        ))
    return updated


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="v0.2 PR watcher for u_agents")
    p.add_argument("--once", action="store_true", help="run one pass and exit")
    args = p.parse_args(argv)
    db_client = AgentRunsClient.from_env()
    try:
        updated = check_once(db_client)
        for run in updated:
            print(
                f"{run.repository_full_name}#{run.github_issue_number}: "
                f"phase={run.phase} pr={run.pr_number}",
                file=sys.stderr,
            )
        if args.once:
            return 0
        return 0
    finally:
        db_client.close()


if __name__ == "__main__":
    raise SystemExit(main())
