"""Optional Slack webhook notification for the PR-open transition.

This is a best-effort side-channel on top of the durable ``agent_runs``
transition. The DB row reaching ``status = 'pr_open'`` with ``pr_number`` set
(via :meth:`AgentRunsClient.mark_pr_open`) remains the source of truth and the
PR-watcher hand-off; Slack delivery never gates it:

* When ``U_AGENTS_SLACK_WEBHOOK_URL`` is unset the helpers are no-ops, so
  behaviour is identical to before this module existed.
* A delivery failure logs a ``WARN`` to stderr and is swallowed, so the CLI
  still exits successfully once the DB transition has committed.
* The notification is sent at most once per run/PR. ``mark_pr_open`` is also
  used to re-arm the PR watcher after review fixes, so a persisted
  ``slack_pr_open_notified`` metadata marker (carrying the ``pr_number``)
  suppresses duplicate messages on later re-arms. The marker is persisted
  *before* the webhook call, so at-most-once holds even if delivery is
  ambiguous: a delivery that fails after the marker is stored is not retried on
  a later re-arm (the at-most-once guarantee is preferred over re-sending an
  ambiguous webhook).

Only the Python standard library is used (``urllib.request``) so the runner
needs no extra dependency beyond what the DB commands already require.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from typing import Callable, Mapping

from u_agents.agent_runs import AgentRun

ENV_SLACK_WEBHOOK_URL = "U_AGENTS_SLACK_WEBHOOK_URL"
SLACK_PR_OPEN_NOTIFIED_KEY = "slack_pr_open_notified"

_DEFAULT_TIMEOUT_SECONDS = 10.0

# Type of the injectable webhook sender (url, text) -> None.
Poster = Callable[[str, str], None]


def webhook_url_from_env(env: Mapping[str, object] | None = None) -> str | None:
    """Return the configured Slack webhook URL, or ``None`` when unset/blank."""
    source = os.environ if env is None else env
    value = source.get(ENV_SLACK_WEBHOOK_URL, "")
    if not isinstance(value, str) or value.strip() == "":
        return None
    return value.strip()


def already_notified(run: AgentRun, pr_number: int) -> bool:
    """Whether this run already sent a Slack PR-open message for ``pr_number``.

    Reads the persisted ``slack_pr_open_notified`` marker. The marker is keyed
    by ``pr_number`` so a brand-new PR for the same run (unusual, but possible)
    is not silently suppressed by a stale marker.
    """
    metadata = run.metadata or {}
    marker = metadata.get(SLACK_PR_OPEN_NOTIFIED_KEY)
    if isinstance(marker, Mapping):
        return marker.get("pr_number") == pr_number
    return False


def build_pr_open_message(run: AgentRun) -> str:
    """Render the Slack message body for an opened PR."""
    repo = run.repository_full_name
    pr = run.pr_number
    return "\n".join(
        [
            "u_agents opened PR",
            f"{repo}#{run.github_issue_number} -> PR #{pr}",
            f"https://github.com/{repo}/pull/{pr}",
            f"branch: {run.branch_name}",
            f"runner: {run.runner_id} / {run.machine_id}",
        ]
    )


def post_to_webhook(
    url: str, text: str, *, timeout: float = _DEFAULT_TIMEOUT_SECONDS
) -> None:
    """POST ``{"text": ...}`` to a Slack incoming webhook.

    Raises on transport or non-2xx HTTP errors; callers treat any exception as
    a non-fatal delivery failure.
    """
    data = json.dumps({"text": text}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        # Slack replies 200 with body "ok"; drain it so the socket closes.
        response.read()


def notify_pr_open(
    db_client,
    run: AgentRun,
    *,
    env: Mapping[str, object] | None = None,
    post: Poster | None = None,
) -> bool:
    """Send a one-time Slack PR-open notification, best-effort.

    Returns ``True`` only when the dedup marker was persisted *and* a message
    was delivered. Returns ``False`` (without raising) when the webhook is
    unset, the run was already notified, the marker could not be persisted, or
    delivery failed. ``post`` is injectable for tests; it defaults to
    :func:`post_to_webhook`.
    """
    url = webhook_url_from_env(env)
    if url is None or run.pr_number is None:
        return False
    if already_notified(run, run.pr_number):
        return False

    # Persist the dedup marker BEFORE delivering, so the at-most-once guarantee
    # is durable: once the marker is stored, a later mark_pr_open re-arm sees it
    # and never re-sends, even if this delivery turns out ambiguous. If the
    # marker cannot be persisted we skip the send entirely rather than risk an
    # un-suppressable duplicate.
    try:
        db_client.merge_metadata(
            run.repository_full_name,
            run.github_issue_number,
            {SLACK_PR_OPEN_NOTIFIED_KEY: {"pr_number": run.pr_number}},
        )
    except Exception as exc:  # noqa: BLE001 - DB row already committed pr_open
        print(
            f"WARN: Slack PR-open notify marker persist failed for "
            f"{run.repository_full_name}#{run.github_issue_number} "
            f"(PR #{run.pr_number}); skipping Slack send: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return False

    sender = post if post is not None else post_to_webhook
    try:
        sender(url, build_pr_open_message(run))
    except Exception as exc:  # noqa: BLE001 - delivery is best-effort
        # The marker is already stored, so this is not retried on a later
        # re-arm: at-most-once is preferred over re-sending an ambiguous webhook.
        print(
            f"WARN: Slack PR-open notification failed for "
            f"{run.repository_full_name}#{run.github_issue_number} "
            f"(PR #{run.pr_number}): {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return False
    return True
