#!/usr/bin/env python3
"""DB-backed PR watcher for u_agents."""
from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from u_agents.agent_runs import AgentRun, AgentRunsClient
from u_agents.contract import pm_pane_target
from u_agents.control_plane import decide_pr_watch_phase


# Verdicts produced by the validation gate. Only ``valid_must_fix`` is eligible
# for an automated fix attempt, and only once per stable comment identity.
REVIEW_VERDICTS = (
    "valid_must_fix",
    "valid_optional",
    "invalid",
    "needs_user_judgment",
)


@dataclass(frozen=True)
class ReviewComment:
    """A PR review comment to be triaged before any automated handling.

    ``source`` is ``inline`` (per-file/line review comment), ``comment``
    (top-level PR comment), or ``latest_review`` (a review summary). The stable
    key is the GitHub comment id plus a body hash, so a re-posted identical
    comment maps to the same key while an edited body becomes a new candidate.
    """

    comment_id: str
    body: str
    source: str
    path: str | None = None
    line: int | None = None
    author: str = ""
    author_type: str = ""
    state: str = ""

    @property
    def body_hash(self) -> str:
        return hashlib.sha256(self.body.encode("utf-8", "replace")).hexdigest()

    @property
    def stable_key(self) -> str:
        return f"{self.comment_id}:{self.body_hash[:12]}"


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
    review_comments: tuple[ReviewComment, ...] = ()


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

# Phrase-anchored "this was already dealt with / does not apply" markers. These
# must NOT contain the bare words "addressed" or "resolved": a bare substring
# match silently swallows forward-looking, actionable comments such as
# "this must be addressed before merge" or "blocking bug should be resolved".
# Only past/dismissive phrasings count as dismissive.
_DISMISSIVE_MARKERS = (
    "already addressed",
    "addressed already",
    "has been addressed",
    "have been addressed",
    "was addressed",
    "were addressed",
    "already resolved",
    "resolved already",
    "has been resolved",
    "have been resolved",
    "was resolved",
    "were resolved",
    "outdated",
    "wontfix",
    "won't fix",
    "stale",
    "rejected",
)
_NON_MUST_FIX_MARKERS = (
    "optional",
    "non-blocking",
    "nonblocking",
    "nit:",
) + _DISMISSIVE_MARKERS


def _comment_body(item) -> str:
    if not isinstance(item, dict):
        return ""
    return str(item.get("body") or "")


def _comment_key(prefix: str, item: dict, fallback_index: int) -> str:
    value = item.get("id") or item.get("databaseId") or item.get("url")
    if value:
        return f"{prefix}:{value}"
    return f"{prefix}:index-{fallback_index}"


def _body_is_validation_candidate(body: str) -> bool:
    """Whether a top-level comment/review body should be routed to validation.

    A body is a candidate when it carries a must-fix marker
    (``_MUST_FIX_MARKERS``) or a forward-looking, actionable phrasing
    (``_FORWARD_ACTION_MARKERS`` -- e.g. "this must be addressed before merge",
    "blocking bug should be resolved"), so it becomes a ``ReviewComment`` object
    and reaches the validation gate instead of being silently ignored on the way
    to ready_to_merge. Dismissive/optional bodies (``_NON_MUST_FIX_MARKERS``)
    are suppressed and take precedence over any must-fix/forward-action token.
    """
    normalized = body.lower().replace("_", "-")
    if any(marker in normalized for marker in _NON_MUST_FIX_MARKERS):
        return False
    if any(marker in normalized for marker in _MUST_FIX_MARKERS):
        return True
    return any(marker in normalized for marker in _FORWARD_ACTION_MARKERS)


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
            if state == "CHANGES_REQUESTED" or _body_is_validation_candidate(body):
                keys.append(_comment_key(prefix, item, index))
    return tuple(keys)


# ---------------------------------------------------------------------------
# Validation gate + triage for PR review comments
# ---------------------------------------------------------------------------

# Reuse the phrase-anchored dismissive set so "this must be addressed before
# merge" / "blocking bug should be resolved" are never classified invalid from a
# bare "addressed"/"resolved" substring.
_INVALID_MARKERS = _DISMISSIVE_MARKERS
_OPTIONAL_MARKERS = ("optional", "non-blocking", "nonblocking", "nit:", "nit ")

# Forward-looking, actionable phrasings that are NOT must-fix markers on their
# own (no "blocking"/"must fix" token) but clearly demand a change. Under the
# conservative default these escalate to needs_user_judgment instead of being
# silently treated as optional.
_FORWARD_ACTION_MARKERS = (
    "must be addressed",
    "should be addressed",
    "needs to be addressed",
    "must be resolved",
    "should be resolved",
    "needs to be resolved",
    "must be fixed",
    "should be fixed",
    "needs to be fixed",
    "before merge",
    "before merging",
)


def default_validate_comment(comment: ReviewComment) -> str:
    """Conservative runtime classification of a single review comment.

    This never returns ``valid_must_fix``: comments are not always correct, so
    the runtime watcher must not auto-fix based on marker text, a
    ``CHANGES_REQUESTED`` review summary, high-priority styling, or bot
    authorship alone. A real ``valid_must_fix`` verdict comes from an explicit
    validator (an agent / the PM) injected by the caller.

    The default stance is to validate, not to skip. Only two kinds of comment
    are dropped here without reaching the PM: ones that are clearly
    obsolete/dismissed (``invalid``) and ones that are explicitly optional or
    have no body (``valid_optional``). Everything else with a body -- including
    a plain inline comment that carries no marker text -- is escalated as
    ``needs_user_judgment`` so it reaches the PM validation gate instead of
    being silently downgraded to optional and ignored. The PM then applies the
    stricter "address unless clearly invalid" policy (see
    ``build_validation_handoff_prompt``).
    """
    state = (comment.state or "").upper()
    if state == "CHANGES_REQUESTED":
        # A CHANGES_REQUESTED review summary / reviewDecision is not a concrete
        # validated change; surface the decision rather than auto-fixing.
        return "needs_user_judgment"
    body = (comment.body or "").strip()
    if not body:
        # Nothing actionable (e.g. an APPROVED review with no body).
        return "valid_optional"
    normalized = body.lower().replace("_", "-")
    if any(marker in normalized for marker in _INVALID_MARKERS):
        # Clearly obsolete / dismissed (already addressed, outdated, wontfix...).
        return "invalid"
    if any(marker in normalized for marker in _OPTIONAL_MARKERS):
        # Explicitly optional / non-blocking / nit.
        return "valid_optional"
    # Anything else with a body is actionable but unconfirmed: route it to the
    # PM validation gate rather than auto-fixing (bot/marker/forward-action
    # text) or silently treating it as optional (plain comments). Not being
    # certain is not a reason to skip a comment.
    return "needs_user_judgment"


@dataclass(frozen=True)
class CommentTriage:
    bookkeeping: dict
    actionable_keys: list
    needs_judgment_keys: list
    # valid_must_fix comments still present this pass that were already attempted
    # once: not auto-fixed again, but not silently ignored either.
    unresolved_keys: list = field(default_factory=list)
    invalid_keys: list = field(default_factory=list)
    optional_keys: list = field(default_factory=list)


def triage_review_comments(
    comments,
    prior_bookkeeping,
    validate: Callable[[ReviewComment], str] = default_validate_comment,
) -> CommentTriage:
    """Run review comments through the validation gate with at-most-once memory.

    ``prior_bookkeeping`` is the persisted per-comment state keyed by
    ``ReviewComment.stable_key`` (id + body hash). A ``valid_must_fix`` comment
    is only ``actionable`` if it has not already been attempted under the same
    key; if it was attempted and is still present it is reported as
    ``unresolved`` instead (do not auto-fix again, but do not ignore it). An
    edited body produces a new key, so it is treated as a fresh candidate.

    Prior bookkeeping is merged forward, not replaced: a pass that sees an
    empty or partial comment list must not drop previously recorded
    verdict/attempted state, or the at-most-once guarantee would weaken.
    """
    if not isinstance(prior_bookkeeping, Mapping):
        prior_bookkeeping = {}
    # Start from prior state so historical (esp. attempted) keys survive even
    # when the current fetch returns fewer/no comments.
    bookkeeping: dict = {
        k: dict(v) for k, v in prior_bookkeeping.items() if isinstance(v, Mapping)
    }
    actionable: list = []
    needs_judgment: list = []
    unresolved: list = []
    invalid_keys: list = []
    optional_keys: list = []
    for comment in comments:
        key = comment.stable_key
        verdict = validate(comment)
        if verdict not in REVIEW_VERDICTS:
            verdict = "needs_user_judgment"
        prior = prior_bookkeeping.get(key)
        attempted = bool(prior.get("attempted")) if isinstance(prior, Mapping) else False
        handed_off = bool(prior.get("handed_off")) if isinstance(prior, Mapping) else False
        bookkeeping[key] = {
            "verdict": verdict,
            "attempted": attempted,
            "handed_off": handed_off,
            "comment_id": comment.comment_id,
            "body_hash": comment.body_hash[:12],
            "source": comment.source,
            "path": comment.path,
            "line": comment.line,
        }
        if verdict == "valid_must_fix":
            if attempted:
                unresolved.append(key)
            else:
                actionable.append(key)
        elif verdict == "needs_user_judgment":
            needs_judgment.append(key)
        elif verdict == "invalid":
            invalid_keys.append(key)
        elif verdict == "valid_optional":
            optional_keys.append(key)
    return CommentTriage(
        bookkeeping=bookkeeping,
        actionable_keys=actionable,
        needs_judgment_keys=needs_judgment,
        unresolved_keys=unresolved,
        invalid_keys=invalid_keys,
        optional_keys=optional_keys,
    )


# "could not resolve to" matches GitHub GraphQL missing-resource errors
# (e.g. "Could not resolve to a PullRequest ..."). It deliberately excludes
# transient DNS/network failures like "Could not resolve host: api.github.com".
_PR_ABSENCE_MARKERS = ("not found", "could not resolve to", "404")

# Fields requested from `gh pr view --json`. The current gh CLI does NOT expose
# a `merged` boolean field; requesting it fails with `Unknown JSON field:
# "merged"` (exit 1), which the absence markers above do not match, so the
# watcher would defer the run forever and never progress. Merged/closed/open
# state is instead inferred from the supported `state` (OPEN/CLOSED/MERGED) and
# `mergedAt` fields. Keep this list to fields gh actually supports.
PR_VIEW_JSON_FIELDS = (
    "number",
    "headRefName",
    "state",
    "mergedAt",
    "statusCheckRollup",
    "reviewDecision",
    "comments",
    "latestReviews",
)


def _author_login_type(item: dict) -> tuple[str, str]:
    """Return (login, type) from a GitHub comment/review item.

    Inline review comments expose ``user``; ``gh pr view`` comments/reviews
    expose ``author``. Bot accounts are reported as type ``Bot`` by the REST
    API, but the GraphQL author shape may omit it, so fall back to the
    ``[bot]`` login suffix.
    """
    author = item.get("user")
    if not isinstance(author, dict):
        author = item.get("author")
    if not isinstance(author, dict):
        author = {}
    login = str(author.get("login") or "")
    atype = str(author.get("type") or "")
    if not atype and login.endswith("[bot]"):
        atype = "Bot"
    return login, atype


def fetch_review_comments(repository_full_name: str, pr_number: int) -> tuple[ReviewComment, ...]:
    """Fetch inline PR review comments (per-file/line) via the REST API.

    ``gh pr view`` only exposes top-level PR comments and review summaries, not
    the inline review comments attached to specific diff lines. Those live at
    ``/repos/{owner}/{repo}/pulls/{n}/comments``.

    A failed call or malformed/non-list output is ambiguous (it is not proof
    the PR has no inline comments), so this raises ``RuntimeError``. The PR
    already exists at this point (``gh pr view`` succeeded), so the caller
    treats the failure as transient and defers the run instead of mutating DB
    state as if there were nothing to validate.
    """
    res = _run([
        "gh", "api",
        f"repos/{repository_full_name}/pulls/{pr_number}/comments?per_page=100",
    ])
    if res.returncode != 0:
        raise RuntimeError(
            f"gh api inline review comments failed for "
            f"{repository_full_name}#{pr_number} (exit {res.returncode}); "
            f"treating as transient: {(res.stderr or '').strip()}"
        )
    try:
        data = json.loads(res.stdout or "[]")
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"gh api returned unparseable inline review comments for "
            f"{repository_full_name}#{pr_number}: {e}"
        ) from e
    if not isinstance(data, list):
        raise RuntimeError(
            f"gh api returned non-list inline review comments for "
            f"{repository_full_name}#{pr_number}: {type(data).__name__}"
        )
    out: list[ReviewComment] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        cid = item.get("id")
        if cid is None:
            continue
        login, atype = _author_login_type(item)
        line = item.get("line")
        if line is None:
            line = item.get("original_line")
        out.append(ReviewComment(
            comment_id=str(cid),
            body=str(item.get("body") or ""),
            source="inline",
            path=item.get("path"),
            line=line,
            author=login,
            author_type=atype,
        ))
    return tuple(out)


def _top_level_review_comments(data: dict) -> tuple[ReviewComment, ...]:
    """Represent must-fix-looking top-level comments / review summaries as
    ``ReviewComment`` objects so they pass through the same validation gate as
    inline comments instead of auto-triggering a fix.

    Items selected for validation are those a validation candidate predicate
    flags: top-level comments with a must-fix or forward-action signal,
    ``CHANGES_REQUESTED`` review summaries, and review summaries with such a
    signal. Forward-looking phrasings ("must be addressed before merge") count
    as candidates so they are not dropped before validation. A bare
    ``reviewDecision == CHANGES_REQUESTED`` (with no concrete comment) becomes a
    sentinel so it escalates to user judgment rather than auto-fixing.
    """
    out: list[ReviewComment] = []
    saw_changes_requested = False

    comments = data.get("comments")
    if isinstance(comments, list):
        for index, item in enumerate(comments):
            if not isinstance(item, dict):
                continue
            body = _comment_body(item)
            if not _body_is_validation_candidate(body):
                continue
            login, atype = _author_login_type(item)
            out.append(ReviewComment(
                comment_id=_comment_key("comment", item, index),
                body=body,
                source="comment",
                author=login,
                author_type=atype,
            ))

    reviews = data.get("latestReviews")
    if isinstance(reviews, list):
        for index, item in enumerate(reviews):
            if not isinstance(item, dict):
                continue
            state = str(item.get("state") or "").upper()
            body = _comment_body(item)
            if state != "CHANGES_REQUESTED" and not _body_is_validation_candidate(body):
                continue
            if state == "CHANGES_REQUESTED":
                saw_changes_requested = True
            login, atype = _author_login_type(item)
            out.append(ReviewComment(
                comment_id=_comment_key("latest_review", item, index),
                body=body,
                source="latest_review",
                author=login,
                author_type=atype,
                state=state,
            ))

    if not saw_changes_requested and data.get("reviewDecision") == "CHANGES_REQUESTED":
        out.append(ReviewComment(
            comment_id="reviewDecision:CHANGES_REQUESTED",
            body="",
            source="review_decision",
            state="CHANGES_REQUESTED",
        ))

    return tuple(out)


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
        "--json", ",".join(PR_VIEW_JSON_FIELDS),
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
    state = str(data.get("state") or "").upper()
    # gh reports a merged PR as state == "MERGED" and also stamps mergedAt;
    # either signal counts as merged. A non-merged terminal PR is "CLOSED".
    merged = state == "MERGED" or bool(data.get("mergedAt"))
    closed = state == "CLOSED"
    must_fix_comment_keys = extract_must_fix_review_comment_keys(data)
    if not must_fix_comment_keys and data.get("reviewDecision") == "CHANGES_REQUESTED":
        must_fix_comment_keys = ("reviewDecision:CHANGES_REQUESTED",)
    # All candidate comments (top-level + reviews + inline) flow through the
    # validation gate; none of them auto-trigger a fix on their own.
    review_comments = _top_level_review_comments(data) + fetch_review_comments(
        repository_full_name, pr_number,
    )
    return PrReality(
        exists=True,
        pr_number=int(data["number"]),
        head_branch=str(data.get("headRefName") or ""),
        merged=merged,
        closed=closed,
        ci_green=_status_checks_green(data.get("statusCheckRollup")),
        must_fix_review_comments=bool(must_fix_comment_keys),
        must_fix_comment_keys=must_fix_comment_keys,
        review_comments=review_comments,
    )


def reconcile_pr_run(
    run: AgentRun,
    reality: PrReality,
    db_client,
    *,
    assign_fix: Callable[[AgentRun, PrReality], None] | None = None,
    dispatch_handoff: Callable[[AgentRun, PrReality, list], bool] | None = None,
    validate_comment: Callable[[ReviewComment], str] = default_validate_comment,
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

    prior_bookkeeping = {}
    if isinstance(run.metadata, Mapping):
        prior_bookkeeping = run.metadata.get("pr_review_comments") or {}
    triage = triage_review_comments(
        reality.review_comments, prior_bookkeeping, validate_comment,
    )

    # Only validated must-fix comments that have not yet been auto-fixed are
    # eligible to trigger a fix. The legacy reality.must_fix_review_comments
    # signal no longer drives fixing directly: those raw comments are routed
    # through the validation gate as ReviewComment objects instead.
    must_fix = bool(triage.actionable_keys)
    decision = decide_pr_watch_phase(
        pr_merged=reality.merged,
        ci_green=reality.ci_green,
        must_fix_review_comments=must_fix,
        pr_review_fix_rounds=run.pr_review_fix_rounds,
    )

    # Mark the fresh actionable comments as attempted only when this pass is
    # actually going to assign a fix round, so each comment id+hash is auto-
    # fixed at most once across passes.
    if decision.increment_fix_rounds:
        for key in triage.actionable_keys:
            triage.bookkeeping[key]["attempted"] = True

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
            "review_comment_triage": {
                "actionable": list(triage.actionable_keys),
                "unresolved": list(triage.unresolved_keys),
                "needs_user_judgment": list(triage.needs_judgment_keys),
                "invalid": list(triage.invalid_keys),
                "valid_optional": list(triage.optional_keys),
                "handed_off": [
                    k for k in triage.needs_judgment_keys
                    if triage.bookkeeping.get(k, {}).get("handed_off")
                ],
            },
        },
        "pr_review_comments": triage.bookkeeping,
    }

    # Merged wins over everything else.
    if decision.phase == "done":
        return db_client.mark_done(
            run.repository_full_name,
            run.github_issue_number,
            metadata=metadata,
        )

    # A fresh validated must-fix with budget left: assign exactly one fix round.
    if decision.phase == "fixing":
        updated = db_client.update_pr_fields(
            run.repository_full_name,
            run.github_issue_number,
            pr_number=reality.pr_number,
            status=decision.phase,
            increment_fix_rounds=decision.increment_fix_rounds,
            metadata=metadata,
        )
        if assign_fix is not None:
            assign_fix(updated, reality)
        return updated

    # Not fixing this pass. A validated must-fix that was already attempted but
    # is still present must NOT slip through to ready_to_merge: it cannot be
    # auto-fixed again, so escalate to a human.
    if triage.unresolved_keys:
        reason = (
            "valid must-fix PR review comments remain after the automated fix "
            "attempt: " + ", ".join(triage.unresolved_keys[:20])
        )
        return db_client.mark_blocked(
            run.repository_full_name,
            run.github_issue_number,
            reason,
            metadata=metadata,
        )

    # Comments needing a human/agent decision. With a live ``dispatch_handoff``
    # the watcher hands the *fresh* (not-yet-dispatched) keys to the existing PM
    # pane for validation+fix instead of dead-ending. Keys already handed off
    # but still ambiguous escalate to a human rather than being re-sent every
    # tick. Without a dispatcher (the conservative default / unit tests) this
    # still blocks for user judgment.
    if triage.needs_judgment_keys:
        fresh = [
            k for k in triage.needs_judgment_keys
            if not triage.bookkeeping.get(k, {}).get("handed_off")
        ]
        if fresh and dispatch_handoff is not None:
            # Deliver the validation prompt first; only persist the handoff if
            # delivery succeeded so a transient tmux failure is retried next
            # tick rather than silently consuming the one-shot handoff.
            delivered = dispatch_handoff(run, reality, fresh)
            if delivered:
                for key in fresh:
                    triage.bookkeeping[key]["handed_off"] = True
                metadata["pr_watcher"]["review_comment_triage"]["handed_off"] = [
                    k for k in triage.needs_judgment_keys
                    if triage.bookkeeping.get(k, {}).get("handed_off")
                ]
                # Park the run out of the watch set while the PM validates/fixes.
                # The handoff prompt instructs the PM to re-arm via mark_pr_open
                # (status -> pr_open) when done, so the watcher re-checks; if the
                # same keys are still ambiguous then, they will have handed_off
                # set and escalate below instead of looping.
                return db_client.update_pr_fields(
                    run.repository_full_name,
                    run.github_issue_number,
                    pr_number=reality.pr_number,
                    status="fixing",
                    metadata=metadata,
                )
            # Delivery failed: keep watching and retry next pass (handed_off
            # stays unset for these keys).
            return db_client.update_pr_fields(
                run.repository_full_name,
                run.github_issue_number,
                pr_number=reality.pr_number,
                status="pr_watching",
                metadata=metadata,
            )
        reason = (
            "PR review comments need user judgment before automated handling: "
            + ", ".join(triage.needs_judgment_keys[:20])
        )
        return db_client.mark_blocked(
            run.repository_full_name,
            run.github_issue_number,
            reason,
            metadata=metadata,
        )

    # Round-cap block (fresh actionable must-fix but no budget left).
    if decision.phase == "blocked":
        return db_client.mark_blocked(
            run.repository_full_name,
            run.github_issue_number,
            decision.block_reason,
            metadata=metadata,
        )
    return db_client.update_pr_fields(
        run.repository_full_name,
        run.github_issue_number,
        pr_number=reality.pr_number,
        status=decision.phase,
        increment_fix_rounds=decision.increment_fix_rounds,
        metadata=metadata,
    )


def check_once(
    db_client,
    *,
    fetch_reality: Callable[[str, int], PrReality] = fetch_pr_reality,
    assign_fix: Callable[[AgentRun, PrReality], None] | None = None,
    dispatch_handoff: Callable[[AgentRun, PrReality, list], bool] | None = None,
    validate_comment: Callable[[ReviewComment], str] = default_validate_comment,
) -> list[AgentRun]:
    updated: list[AgentRun] = []
    for run in db_client.list_pr_watch_runs():
        if run.pr_number is None:
            updated.append(reconcile_pr_run(
                run,
                PrReality(False, 0, "", False, False, False),
                db_client,
                assign_fix=assign_fix,
                dispatch_handoff=dispatch_handoff,
                validate_comment=validate_comment,
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
            dispatch_handoff=dispatch_handoff,
            validate_comment=validate_comment,
        ))
    return updated


# ---------------------------------------------------------------------------
# Live (production) handoff to the existing PM tmux pane
# ---------------------------------------------------------------------------
#
# The watcher does not own its own agent. When a review comment cannot be
# auto-classified (the conservative default escalates everything actionable to
# ``needs_user_judgment``), the live watcher hands the comment(s) to the PM pane
# that already owns the run (``run.pm_pane`` / ``pm_pane_target(run.tmux_window)``)
# using the same tmux delivery primitive the launcher uses to seed the PM.
#
# Duplicate handoffs are prevented by the per-comment ``handed_off`` flag in
# ``pr_review_comments`` bookkeeping: only keys without it are dispatched, and a
# successful delivery parks the run in ``status='fixing'`` so it leaves the watch
# set until the PM re-arms it via ``mark_pr_open`` (status -> ``pr_open``). The
# same key, if still ambiguous on re-entry, escalates to a human instead of
# being re-sent.


# Directory containing the ``u_agents`` package (the dotfiles checkout root is
# its parent). Used to build the exact mark_pr_open re-arm command for the PM,
# which runs inside the target repo worktree where ``u_agents`` is not on the
# path and a bare ``python3`` may lack ``psycopg``.
_PACKAGE_DIR = Path(__file__).resolve().parent


def mark_pr_open_command(repository_full_name: str, issue_number: int, pr_number: int) -> str:
    """Exact, shell-quoted re-arm command mirroring the PM prompt contract.

    Uses ``PYTHONPATH=<dotfiles root>`` and the running interpreter
    (``sys.executable``, which already imported psycopg) instead of a bare
    ``python -m u_agents.mark_pr_open``.
    """
    root = shlex.quote(str(_PACKAGE_DIR.parent))
    python = shlex.quote(sys.executable)
    return (
        f"PYTHONPATH={root} {python} -m u_agents.mark_pr_open "
        f"--repo {repository_full_name} --issue {issue_number} --pr {pr_number}"
    )


def _comments_by_key(reality: PrReality) -> dict:
    return {c.stable_key: c for c in reality.review_comments}


def _format_comment_lines(reality: PrReality, keys: list) -> str:
    by_key = _comments_by_key(reality)
    lines: list[str] = []
    for key in keys:
        c = by_key.get(key)
        if c is None:
            lines.append(f"- [{key}] (comment no longer present in latest fetch)")
            continue
        loc = ""
        if c.path:
            loc = f" {c.path}" + (f":{c.line}" if c.line is not None else "")
        body = " ".join((c.body or "").split())
        if len(body) > 400:
            body = body[:400] + "…"
        lines.append(f"- [{key}]{loc} ({c.source}) {body}")
    return "\n".join(lines)


def build_validation_handoff_prompt(
    run: AgentRun, reality: PrReality, keys: list
) -> str:
    """Prompt that asks the existing PM to validate review comments first.

    Each comment is referenced by its stable ``id:body-hash`` key so the PM can
    record a verdict per key and address each at most once.
    """
    listing = _format_comment_lines(reality, keys)
    rearm = mark_pr_open_command(
        run.repository_full_name, run.github_issue_number, reality.pr_number,
    )
    return (
        "u-agents PR watcher handoff: validate PR review comments for "
        f"{run.repository_full_name}#{run.github_issue_number} "
        f"(PR #{reality.pr_number}).\n\n"
        "These review comments are NOT pre-approved, but your DEFAULT STANCE is "
        "to ADDRESS them. Validate each before changing any code; only skip a "
        "comment when it is clearly invalid, explicitly optional, or a "
        "product/spec decision you cannot make:\n\n"
        f"{listing}\n\n"
        "Rules:\n"
        "1. Default stance: address every listed comment unless it is clearly "
        "invalid. A comment being inconvenient, or you not being fully certain, "
        "is NOT a reason to skip it.\n"
        "2. Validate each listed comment first (a comment is not automatically "
        "correct), then classify it by its [id:hash] key as exactly one of:\n"
        "   - valid_must_fix: the DEFAULT verdict for anything actionable that "
        "is not clearly invalid, explicitly optional, or a product/spec "
        "decision.\n"
        "   - valid_optional: RARE. Only comments explicitly marked "
        "optional / non-blocking / nit, or whose value is purely cosmetic AND "
        "out of the current scope.\n"
        "   - invalid: ONLY when the comment is factually wrong, contradicts "
        "the issue/spec, would break behavior, is already obsolete/addressed, "
        "or is impossible to apply (give the concrete reason).\n"
        "   - needs_user_judgment: ONLY for product/spec decisions, scope "
        "changes, or genuine tradeoffs you cannot decide as the implementation "
        "agent.\n"
        "3. If you are unsure between valid_must_fix and valid_optional, choose "
        "valid_must_fix. Do not downgrade a real comment to optional to avoid "
        "work.\n"
        "4. Do NOT change code for invalid, valid_optional, or "
        "needs_user_judgment comments.\n"
        "5. Address every valid_must_fix comment. Address each comment (by its "
        "[id:hash] key above) at most once; if you already addressed that exact "
        "key in a previous round, do not redo it.\n"
        "6. Record your verdict for each key in your PR/issue report "
        "(key -> verdict + one-line reason). For invalid / valid_optional / "
        "needs_user_judgment the reason must justify NOT fixing it.\n"
        "7. After addressing valid_must_fix comments and pushing, re-arm the "
        "watcher by running exactly this full command; do not replace it with "
        "a bare interpreter invocation:\n"
        f"       {rearm}\n"
        "8. For needs_user_judgment comments, comment on the issue asking the "
        "user; do not guess and do not silently skip.\n"
    )


def build_fix_prompt(run: AgentRun, reality: PrReality) -> str:
    """Prompt for the valid_must_fix path (used when an explicit validator has
    already confirmed must-fix comments). Lists all current review comments and
    asks the PM to address the validated must-fix ones and re-arm the watcher.
    """
    keys = [c.stable_key for c in reality.review_comments]
    listing = _format_comment_lines(reality, keys)
    rearm = mark_pr_open_command(
        run.repository_full_name, run.github_issue_number, reality.pr_number,
    )
    return (
        "u-agents PR watcher: address validated must-fix review comments for "
        f"{run.repository_full_name}#{run.github_issue_number} "
        f"(PR #{reality.pr_number}).\n\n"
        f"{listing}\n\n"
        "Address each validated must-fix comment exactly once, push, then "
        "re-arm the watcher by running exactly this full command; do not "
        "replace it with a bare interpreter invocation:\n"
        f"       {rearm}\n"
    )


def _send_pm_prompt(run: AgentRun, prompt: str) -> bool:
    """Deliver ``prompt`` to the run's existing PM pane via tmux.

    Reuses the launcher's tmux delivery (readiness check + buffer paste) so the
    watcher does not reimplement pane plumbing. Returns True on delivery,
    False on any tmux/pane failure (logged) so the caller can retry next pass.
    """
    from u_agents import launcher

    window = run.tmux_window
    target = run.pm_pane or pm_pane_target(window)
    try:
        launcher.send_prompt(window, prompt, dry_run=False)
        print(
            f"u-agents pr-watcher: dispatched prompt to {target} for "
            f"{run.repository_full_name}#{run.github_issue_number}",
            file=sys.stderr,
        )
        return True
    except Exception as e:
        print(
            f"WARN: could not deliver pr-watcher prompt to {target} for "
            f"{run.repository_full_name}#{run.github_issue_number}: "
            f"{type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return False


def live_dispatch_handoff(run: AgentRun, reality: PrReality, keys: list) -> bool:
    """Production handoff: send the validation prompt to the PM pane."""
    return _send_pm_prompt(run, build_validation_handoff_prompt(run, reality, keys))


def live_assign_fix(run: AgentRun, reality: PrReality) -> None:
    """Production fix dispatch for the valid_must_fix path."""
    _send_pm_prompt(run, build_fix_prompt(run, reality))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="v0.2 PR watcher for u_agents")
    p.add_argument("--once", action="store_true", help="run one pass and exit")
    args = p.parse_args(argv)
    db_client = AgentRunsClient.from_env()
    try:
        updated = check_once(
            db_client,
            assign_fix=live_assign_fix,
            dispatch_handoff=live_dispatch_handoff,
        )
        for run in updated:
            print(
                f"{run.repository_full_name}#{run.github_issue_number}: "
                f"status={run.status} pr={run.pr_number}",
                file=sys.stderr,
            )
        if args.once:
            return 0
        return 0
    finally:
        db_client.close()


if __name__ == "__main__":
    raise SystemExit(main())
