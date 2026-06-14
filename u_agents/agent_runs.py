"""Runtime access layer for the PostgreSQL ``agent_runs`` table."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from u_agents.contract import (
    ConfigError,
    REVIEW_RESULT_RELATIVE_PATH,
    RepoConfig,
    pm_pane_target,
    tmux_window_name,
)
from u_agents.control_plane import (
    AGENT_RUN_STATUSES,
    REVIEW_COMMENT_RESOLUTION_STATUSES,
    REVIEW_COMMENT_SOURCES,
    REVIEW_COMMENT_VERDICTS,
    RunnerIdentity,
    database_url_from_env,
    load_runner_identity,
    validate_identity_value,
    validate_worktree_basename,
)


ACTIVE_STATUSES = (
    "claimed",
    "pm_started",
    "engineering",
    "reviewing",
    "fixing",
    "pr_open",
    "pr_watching",
    "ready_to_merge",
)
TERMINAL_STATUSES = ("blocked", "done", "cancelled")

# Compatibility aliases while the DB contract moves from `phase` to `status`.
ACTIVE_PHASES = ACTIVE_STATUSES
TERMINAL_PHASES = TERMINAL_STATUSES

_REPOSITORY_RE = re.compile(r"^[^/\s]+/[^/\s]+$")


@dataclass(frozen=True)
class AgentRun:
    repository_full_name: str
    github_issue_number: int
    parent_branch: str
    branch_name: str
    phase: str
    runner_id: str
    machine_id: str
    locked_by: str | None
    lease_until: Any
    worktree_basename: str
    tmux_window: str
    pm_pane: str | None = None
    pr_number: int | None = None
    pr_review_fix_rounds: int = 0
    block_reason: str | None = None
    metadata: Mapping[str, Any] | None = None

    @property
    def status(self) -> str:
        return self.phase

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "AgentRun":
        phase_or_status = row.get("phase", row.get("status"))
        return cls(
            repository_full_name=str(row["repository_full_name"]),
            github_issue_number=int(row["github_issue_number"]),
            parent_branch=str(row["parent_branch"]),
            branch_name=str(row["branch_name"]),
            phase=str(phase_or_status),
            runner_id=str(row["runner_id"]),
            machine_id=str(row["machine_id"]),
            locked_by=row.get("locked_by"),
            lease_until=row.get("lease_until"),
            worktree_basename=str(row["worktree_basename"]),
            tmux_window=str(row["tmux_window"]),
            pm_pane=row.get("pm_pane"),
            pr_number=row.get("pr_number"),
            pr_review_fix_rounds=int(row.get("pr_review_fix_rounds") or 0),
            block_reason=row.get("block_reason"),
            metadata=row.get("metadata") or {},
        )


@dataclass(frozen=True)
class ReviewCommentRecord:
    """A durable PR review comment row from ``review_comments``.

    The watcher owns ``watcher_verdict`` (what it observed); the PM owns
    ``pm_decision`` and the ``resolution_status`` lifecycle plus the commit /
    verification evidence. ``comment_key`` (``github_comment_id:body_hash``) is
    the stable identity used across passes and by the PM CLI.
    """

    agent_run_id: str
    github_comment_id: int
    body_hash: str
    comment_key: str
    pr_number: int
    source: str
    watcher_verdict: str
    resolution_status: str
    pm_decision: str | None = None
    handed_off_at: Any = None
    resolved_at: Any = None
    addressed_by_commit_sha: str | None = None
    verification_summary: str | None = None
    verification_refs: Any = None
    original_body: str | None = None
    original_path: str | None = None
    original_line: int | None = None
    original_commit_sha: str | None = None

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "ReviewCommentRecord":
        return cls(
            agent_run_id=str(row["agent_run_id"]),
            github_comment_id=int(row["github_comment_id"]),
            body_hash=str(row["body_hash"]),
            comment_key=str(row["comment_key"]),
            pr_number=int(row["pr_number"]),
            source=str(row["source"]),
            watcher_verdict=str(row["watcher_verdict"]),
            resolution_status=str(row["resolution_status"]),
            pm_decision=row.get("pm_decision"),
            handed_off_at=row.get("handed_off_at"),
            resolved_at=row.get("resolved_at"),
            addressed_by_commit_sha=row.get("addressed_by_commit_sha"),
            verification_summary=row.get("verification_summary"),
            verification_refs=row.get("verification_refs"),
            original_body=row.get("original_body"),
            original_path=row.get("original_path"),
            original_line=row.get("original_line"),
            original_commit_sha=row.get("original_commit_sha"),
        )


@dataclass(frozen=True)
class ClaimPayload:
    repository_full_name: str
    github_issue_number: int
    parent_branch: str
    branch_name: str
    runner_id: str
    machine_id: str
    locked_by: str
    lease_until: datetime
    worktree_basename: str
    tmux_window: str
    review_result_relative_path: str = REVIEW_RESULT_RELATIVE_PATH
    phase: str = "claimed"

    @property
    def status(self) -> str:
        return self.phase


def validate_repository_full_name(value: str) -> str:
    if not isinstance(value, str) or not _REPOSITORY_RE.match(value):
        raise ValueError("repository_full_name must be owner/name with no whitespace")
    return value


def validate_issue_number(value: int) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ValueError("github_issue_number must be a positive integer")
    return value


def validate_nonempty_nowhitespace(value: str, field: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError(f"{field} must be non-empty")
    if any(ch.isspace() for ch in value):
        raise ValueError(f"{field} must not contain whitespace")
    return value


def validate_runner_identity_field(value: str, field: str) -> str:
    value = validate_nonempty_nowhitespace(value, field)
    validate_identity_value(value, field)
    return value


def validate_status(value: str) -> str:
    if value not in AGENT_RUN_STATUSES:
        raise ValueError(f"status must be one of: {', '.join(AGENT_RUN_STATUSES)}")
    return value


def validate_phase(value: str) -> str:
    return validate_status(value)


def _resolve_status(status: str | None, phase: str | None = None) -> str:
    if phase is not None:
        if status is not None and status != phase:
            raise ValueError("status and phase aliases must match when both are set")
        status = phase
    if status is None:
        raise ValueError("status is required")
    return validate_status(status)


def validate_metadata(metadata: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if metadata is None:
        return {}
    if not isinstance(metadata, Mapping):
        raise ValueError("metadata must be a mapping/object")
    json.dumps(dict(metadata))
    return metadata


# ---------------------------------------------------------------------------
# review_comments validation (shared by AgentRunsClient and the PM CLI)
# ---------------------------------------------------------------------------


def validate_github_comment_id(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("github_comment_id must be an integer")
    return value


def validate_body_hash(value: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError("body_hash must be a non-empty string")
    if any(ch.isspace() for ch in value):
        raise ValueError("body_hash must not contain whitespace")
    return value


def validate_comment_key(value: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError("comment_key must be a non-empty string")
    # comment_key is the ``github_comment_id:body_hash`` generated column. The
    # id part may be a signed 64-bit integer (synthetic review signals use
    # deterministic signed ids), so only enforce the colon-delimited shape with
    # non-empty parts rather than the exact id/hash formats.
    head, sep, tail = value.partition(":")
    if not sep or head.strip() == "" or tail.strip() == "":
        raise ValueError(
            "comment_key must be 'github_comment_id:body_hash' with non-empty parts"
        )
    return value


def validate_review_comment_source(value: str) -> str:
    if value not in REVIEW_COMMENT_SOURCES:
        raise ValueError(
            f"source must be one of: {', '.join(REVIEW_COMMENT_SOURCES)}"
        )
    return value


def validate_watcher_verdict(value: str) -> str:
    if value not in REVIEW_COMMENT_VERDICTS:
        raise ValueError(
            f"watcher_verdict must be one of: {', '.join(REVIEW_COMMENT_VERDICTS)}"
        )
    return value


def validate_pm_decision(value: str | None) -> str | None:
    if value is None:
        return None
    if value not in REVIEW_COMMENT_VERDICTS:
        raise ValueError(
            f"pm_decision must be one of: {', '.join(REVIEW_COMMENT_VERDICTS)}"
        )
    return value


def validate_resolution_status(value: str) -> str:
    if value not in REVIEW_COMMENT_RESOLUTION_STATUSES:
        raise ValueError(
            "resolution_status must be one of: "
            + ", ".join(REVIEW_COMMENT_RESOLUTION_STATUSES)
        )
    return value


def validate_verification_refs(refs: Any) -> list:
    """Validate that verification_refs is a JSON array (list)."""
    if refs is None:
        return []
    if not isinstance(refs, (list, tuple)):
        raise ValueError("verification_refs must be a JSON array (list)")
    try:
        json.dumps(list(refs))
    except TypeError as e:
        raise ValueError(
            "verification_refs elements must be JSON-serializable"
        ) from e
    return list(refs)


def _is_blank(value: str | None) -> bool:
    return value is None or str(value).strip() == ""


def validate_review_comment_resolution(
    resolution_status: str,
    *,
    addressed_by_commit_sha: str | None,
    verification_summary: str | None,
) -> None:
    """Enforce the evidence each terminal resolution requires.

    The DB also enforces ``addressed`` requires a commit + verification summary;
    this gives the client and CLI an early, specific error and additionally
    requires a reason (``verification_summary``) for ``rejected`` /
    ``needs_user_judgment`` so a PM cannot silently close a comment.
    """
    validate_resolution_status(resolution_status)
    if resolution_status == "addressed":
        if _is_blank(addressed_by_commit_sha):
            raise ValueError(
                "resolution_status 'addressed' requires addressed_by_commit_sha"
            )
        if _is_blank(verification_summary):
            raise ValueError(
                "resolution_status 'addressed' requires verification_summary"
            )
    elif resolution_status in ("rejected", "needs_user_judgment"):
        if _is_blank(verification_summary):
            raise ValueError(
                f"resolution_status '{resolution_status}' requires a reason in "
                "verification_summary"
            )


def build_claim_payload(
    repo: RepoConfig,
    issue_number: int,
    branch: str,
    identity: RunnerIdentity,
    *,
    lease_seconds: int = 900,
    now: datetime | None = None,
) -> ClaimPayload:
    base = now or datetime.now(timezone.utc)
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive")
    return ClaimPayload(
        repository_full_name=validate_repository_full_name(repo.full_name),
        github_issue_number=validate_issue_number(issue_number),
        parent_branch=validate_nonempty_nowhitespace(
            repo.default_branch, "parent_branch"
        ),
        branch_name=validate_nonempty_nowhitespace(branch, "branch_name"),
        runner_id=validate_runner_identity_field(identity.runner_id, "runner_id"),
        machine_id=validate_runner_identity_field(identity.machine_id, "machine_id"),
        locked_by=validate_nonempty_nowhitespace(identity.lock_owner, "locked_by"),
        lease_until=base + timedelta(seconds=lease_seconds),
        worktree_basename=validate_worktree_basename(str(issue_number)),
        tmux_window=validate_nonempty_nowhitespace(
            tmux_window_name(repo, issue_number), "tmux_window"
        ),
    )


def _row_columns() -> str:
    return (
        "repository_full_name, github_issue_number, parent_branch, branch_name, "
        "status AS phase, runner_id, machine_id, locked_by, lease_until, "
        "worktree_basename, tmux_window, pm_pane, pr_number, "
        "pr_review_fix_rounds, block_reason, metadata"
    )


_REVIEW_COMMENT_COLUMNS = (
    "agent_run_id",
    "github_comment_id",
    "body_hash",
    "comment_key",
    "pr_number",
    "source",
    "watcher_verdict",
    "pm_decision",
    "resolution_status",
    "original_body",
    "original_path",
    "original_line",
    "original_commit_sha",
    "handed_off_at",
    "resolved_at",
    "addressed_by_commit_sha",
    "verification_summary",
    "verification_refs",
    "first_seen_at",
    "last_seen_at",
)


def _review_comment_columns(prefix: str = "") -> str:
    dot = f"{prefix}." if prefix else ""
    return ", ".join(f"{dot}{c}" for c in _REVIEW_COMMENT_COLUMNS)


class AgentRunsClient:
    def __init__(self, conn: Any, identity: RunnerIdentity):
        self.conn = conn
        self.identity = identity

    @classmethod
    def from_env(cls, env: Mapping[str, object] | None = None) -> "AgentRunsClient":
        url = database_url_from_env(env)
        identity = load_runner_identity(env)
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ModuleNotFoundError as e:
            raise ConfigError(
                "psycopg is required for u_agents DB runtime access; "
                "install it with `python3 -m pip install 'psycopg[binary]'`"
            ) from e
        return cls(psycopg.connect(url, row_factory=dict_row), identity)

    def close(self) -> None:
        close = getattr(self.conn, "close", None)
        if close is not None:
            close()

    def acquire_claim(self, payload: ClaimPayload) -> AgentRun:
        self._validate_claim_payload(payload)
        sql = f"""
            INSERT INTO agent_runs (
                repository_full_name, github_issue_number, parent_branch,
                branch_name, status, runner_id, machine_id, locked_by,
                lease_until, worktree_basename, tmux_window,
                review_result_relative_path, metadata
            ) VALUES (
                %(repository_full_name)s, %(github_issue_number)s,
                %(parent_branch)s, %(branch_name)s, %(status)s,
                %(runner_id)s, %(machine_id)s, %(locked_by)s,
                %(lease_until)s, %(worktree_basename)s, %(tmux_window)s,
                %(review_result_relative_path)s, '{{}}'::jsonb
            )
            ON CONFLICT (repository_full_name, github_issue_number) DO UPDATE
            SET parent_branch = EXCLUDED.parent_branch,
                branch_name = EXCLUDED.branch_name,
                status = 'claimed',
                runner_id = EXCLUDED.runner_id,
                machine_id = EXCLUDED.machine_id,
                locked_by = EXCLUDED.locked_by,
                lease_until = EXCLUDED.lease_until,
                worktree_basename = EXCLUDED.worktree_basename,
                tmux_window = EXCLUDED.tmux_window,
                pm_pane = NULL,
                block_reason = NULL,
                review_result_relative_path = EXCLUDED.review_result_relative_path,
                metadata = agent_runs.metadata || '{{"reclaimed": true}}'::jsonb
            WHERE agent_runs.lease_until IS NULL
               OR agent_runs.lease_until < now()
               OR agent_runs.locked_by = EXCLUDED.locked_by
               OR agent_runs.status IN ('blocked', 'done', 'cancelled')
            RETURNING {_row_columns()}
        """
        row = self._fetch_one(sql, {**payload.__dict__, "status": payload.status})
        if row is None:
            raise RuntimeError(
                "agent_runs claim lease is held by another runner for "
                f"{payload.repository_full_name}#{payload.github_issue_number}"
            )
        return AgentRun.from_row(row)

    def update_status(
        self,
        repository_full_name: str,
        github_issue_number: int,
        status: str,
        *,
        metadata: Mapping[str, Any] | None = None,
        block_reason: str | None = None,
        clear_lease: bool = False,
    ) -> AgentRun:
        validate_repository_full_name(repository_full_name)
        validate_issue_number(github_issue_number)
        validate_status(status)
        validate_metadata(metadata)
        if status == "blocked" and (block_reason is None or block_reason.strip() == ""):
            raise ValueError("block_reason is required when status is blocked")
        sql = f"""
            UPDATE agent_runs
            SET status = %(status)s,
                block_reason = %(block_reason)s,
                locked_by = CASE WHEN %(clear_lease)s THEN NULL ELSE locked_by END,
                lease_until = CASE WHEN %(clear_lease)s THEN NULL ELSE lease_until END,
                metadata = metadata || %(metadata)s::jsonb
            WHERE repository_full_name = %(repository_full_name)s
              AND github_issue_number = %(github_issue_number)s
            RETURNING {_row_columns()}
        """
        return self._require_row(sql, {
            "repository_full_name": repository_full_name,
            "github_issue_number": github_issue_number,
            "status": status,
            "block_reason": block_reason,
            "clear_lease": clear_lease,
            "metadata": json.dumps(dict(metadata or {})),
        })

    def update_phase(
        self,
        repository_full_name: str,
        github_issue_number: int,
        phase: str,
        *,
        metadata: Mapping[str, Any] | None = None,
        block_reason: str | None = None,
        clear_lease: bool = False,
    ) -> AgentRun:
        return self.update_status(
            repository_full_name,
            github_issue_number,
            phase,
            metadata=metadata,
            block_reason=block_reason,
            clear_lease=clear_lease,
        )

    def update_tmux_coordinates(
        self,
        repository_full_name: str,
        github_issue_number: int,
        *,
        tmux_window: str,
        pm_pane: str | None,
        status: str = "pm_started",
        phase: str | None = None,
    ) -> AgentRun:
        validate_repository_full_name(repository_full_name)
        validate_issue_number(github_issue_number)
        validate_nonempty_nowhitespace(tmux_window, "tmux_window")
        if pm_pane is not None:
            validate_nonempty_nowhitespace(pm_pane, "pm_pane")
        status = _resolve_status(status, phase)
        sql = f"""
            UPDATE agent_runs
            SET status = %(status)s,
                tmux_window = %(tmux_window)s,
                pm_pane = %(pm_pane)s
            WHERE repository_full_name = %(repository_full_name)s
              AND github_issue_number = %(github_issue_number)s
            RETURNING {_row_columns()}
        """
        return self._require_row(sql, {
            "repository_full_name": repository_full_name,
            "github_issue_number": github_issue_number,
            "status": status,
            "tmux_window": tmux_window,
            "pm_pane": pm_pane,
        })

    def mark_pm_started(self, run: AgentRun) -> AgentRun:
        return self.update_tmux_coordinates(
            run.repository_full_name,
            run.github_issue_number,
            tmux_window=run.tmux_window,
            pm_pane=pm_pane_target(run.tmux_window),
            status="pm_started",
        )

    def update_pr_fields(
        self,
        repository_full_name: str,
        github_issue_number: int,
        *,
        pr_number: int | None = None,
        status: str | None = None,
        phase: str | None = None,
        increment_fix_rounds: bool = False,
        block_reason: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> AgentRun:
        validate_repository_full_name(repository_full_name)
        validate_issue_number(github_issue_number)
        if pr_number is not None and pr_number <= 0:
            raise ValueError("pr_number must be positive when set")
        status = (
            _resolve_status(status, phase)
            if status is not None or phase is not None
            else None
        )
        validate_metadata(metadata)
        if status == "blocked" and (block_reason is None or block_reason.strip() == ""):
            raise ValueError("block_reason is required when status is blocked")
        sql = f"""
            UPDATE agent_runs
            SET pr_number = COALESCE(%(pr_number)s, pr_number),
                status = COALESCE(%(status)s, status),
                pr_review_fix_rounds = pr_review_fix_rounds
                    + CASE WHEN %(increment_fix_rounds)s THEN 1 ELSE 0 END,
                block_reason = %(block_reason)s,
                metadata = metadata || %(metadata)s::jsonb
            WHERE repository_full_name = %(repository_full_name)s
              AND github_issue_number = %(github_issue_number)s
            RETURNING {_row_columns()}
        """
        return self._require_row(sql, {
            "repository_full_name": repository_full_name,
            "github_issue_number": github_issue_number,
            "pr_number": pr_number,
            "status": status,
            "increment_fix_rounds": increment_fix_rounds,
            "block_reason": block_reason,
            "metadata": json.dumps(dict(metadata or {})),
        })

    def merge_metadata(
        self,
        repository_full_name: str,
        github_issue_number: int,
        metadata: Mapping[str, Any],
    ) -> AgentRun:
        validate_repository_full_name(repository_full_name)
        validate_issue_number(github_issue_number)
        validate_metadata(metadata)
        sql = f"""
            UPDATE agent_runs
            SET metadata = metadata || %(metadata)s::jsonb
            WHERE repository_full_name = %(repository_full_name)s
              AND github_issue_number = %(github_issue_number)s
            RETURNING {_row_columns()}
        """
        return self._require_row(sql, {
            "repository_full_name": repository_full_name,
            "github_issue_number": github_issue_number,
            "metadata": json.dumps(dict(metadata)),
        })

    def mark_pr_open(
        self,
        repository_full_name: str,
        github_issue_number: int,
        *,
        pr_number: int,
        metadata: Mapping[str, Any] | None = None,
    ) -> AgentRun:
        """Durably record that a PR was opened for this run.

        Sets ``status = 'pr_open'`` and ``pr_number`` so the PR watcher's
        ``list_pr_watch_runs`` query (status in pr_open/pr_watching/ready_to_merge
        AND pr_number IS NOT NULL) picks the run up. This is the persisted
        hand-off from PM/automation to the PR watcher; it must not rely on PM
        prompt memory alone.
        """
        observation: dict[str, Any] = dict(metadata or {})
        observation["pr_open"] = {"pr_number": pr_number}
        return self.update_pr_fields(
            repository_full_name,
            github_issue_number,
            pr_number=pr_number,
            status="pr_open",
            metadata=observation,
        )

    def record_observation(
        self,
        repository_full_name: str,
        github_issue_number: int,
        observation: Mapping[str, Any],
    ) -> AgentRun:
        return self.update_status(
            repository_full_name,
            github_issue_number,
            status=self.get_run(repository_full_name, github_issue_number).status,
            metadata={"observations": dict(observation)},
        )

    def mark_blocked(
        self,
        repository_full_name: str,
        github_issue_number: int,
        reason: str,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> AgentRun:
        return self.update_phase(
            repository_full_name,
            github_issue_number,
            "blocked",
            block_reason=reason,
            metadata=metadata,
            clear_lease=True,
        )

    def mark_done(
        self,
        repository_full_name: str,
        github_issue_number: int,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> AgentRun:
        return self.update_phase(
            repository_full_name,
            github_issue_number,
            "done",
            metadata=metadata,
            clear_lease=True,
        )

    def cancel_run(
        self,
        repository_full_name: str,
        github_issue_number: int,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> AgentRun:
        return self.update_phase(
            repository_full_name,
            github_issue_number,
            "cancelled",
            metadata=metadata,
            clear_lease=True,
        )

    def get_run(self, repository_full_name: str, github_issue_number: int) -> AgentRun:
        validate_repository_full_name(repository_full_name)
        validate_issue_number(github_issue_number)
        sql = f"""
            SELECT {_row_columns()}
            FROM agent_runs
            WHERE repository_full_name = %(repository_full_name)s
              AND github_issue_number = %(github_issue_number)s
        """
        return self._require_row(sql, {
            "repository_full_name": repository_full_name,
            "github_issue_number": github_issue_number,
        })

    def list_active_runs(self) -> list[AgentRun]:
        sql = f"""
            SELECT {_row_columns()}
            FROM agent_runs
            WHERE status = ANY(%(statuses)s)
            ORDER BY updated_at ASC
        """
        return [
            AgentRun.from_row(r)
            for r in self._fetch_all(sql, {"statuses": list(ACTIVE_STATUSES)})
        ]

    def list_stale_runs(self) -> list[AgentRun]:
        sql = f"""
            SELECT {_row_columns()}
            FROM agent_runs
            WHERE status = ANY(%(statuses)s)
              AND lease_until IS NOT NULL
              AND lease_until < now()
            ORDER BY lease_until ASC
        """
        return [
            AgentRun.from_row(r)
            for r in self._fetch_all(sql, {"statuses": list(ACTIVE_STATUSES)})
        ]

    def list_pr_watch_runs(self) -> list[AgentRun]:
        sql = f"""
            SELECT {_row_columns()}
            FROM agent_runs
            WHERE status IN ('pr_open', 'pr_watching', 'ready_to_merge')
              AND pr_number IS NOT NULL
            ORDER BY updated_at ASC
        """
        return [AgentRun.from_row(r) for r in self._fetch_all(sql, {})]

    # ----- review_comments -------------------------------------------------

    def upsert_review_comment(
        self,
        repository_full_name: str,
        github_issue_number: int,
        *,
        github_comment_id: int,
        body_hash: str,
        pr_number: int,
        source: str,
        watcher_verdict: str,
        original_body: str | None = None,
        original_path: str | None = None,
        original_line: int | None = None,
        original_commit_sha: str | None = None,
    ) -> ReviewCommentRecord:
        """Record a review comment the watcher saw this pass.

        First detection inserts the row; later passes update only the
        watcher-observed fields (``watcher_verdict``, ``source``, ``pr_number``,
        the captured original_* fields) and ``last_seen_at``. The PM-owned
        resolution lifecycle (``pm_decision``, ``resolution_status``,
        ``handed_off_at``, ``resolved_at``, commit, verification) is preserved
        across passes so an addressed/rejected comment is never silently reset
        to ``unresolved`` by a later watcher observation.
        """
        validate_repository_full_name(repository_full_name)
        validate_issue_number(github_issue_number)
        validate_github_comment_id(github_comment_id)
        validate_body_hash(body_hash)
        if not isinstance(pr_number, int) or isinstance(pr_number, bool) or pr_number <= 0:
            raise ValueError("pr_number must be a positive integer")
        validate_review_comment_source(source)
        validate_watcher_verdict(watcher_verdict)
        sql = f"""
            INSERT INTO review_comments (
                agent_run_id, github_comment_id, body_hash, pr_number, source,
                watcher_verdict, original_body, original_path, original_line,
                original_commit_sha, last_seen_at
            )
            SELECT run_id, %(github_comment_id)s, %(body_hash)s, %(pr_number)s,
                   %(source)s, %(watcher_verdict)s, %(original_body)s,
                   %(original_path)s, %(original_line)s, %(original_commit_sha)s,
                   now()
            FROM agent_runs
            WHERE repository_full_name = %(repository_full_name)s
              AND github_issue_number = %(github_issue_number)s
            ON CONFLICT ON CONSTRAINT review_comments_pkey DO UPDATE
            SET pr_number = EXCLUDED.pr_number,
                source = EXCLUDED.source,
                watcher_verdict = EXCLUDED.watcher_verdict,
                original_body = EXCLUDED.original_body,
                original_path = EXCLUDED.original_path,
                original_line = EXCLUDED.original_line,
                original_commit_sha = COALESCE(
                    EXCLUDED.original_commit_sha,
                    review_comments.original_commit_sha
                ),
                last_seen_at = now()
            RETURNING {_review_comment_columns()}
        """
        row = self._fetch_one(sql, {
            "repository_full_name": repository_full_name,
            "github_issue_number": github_issue_number,
            "github_comment_id": github_comment_id,
            "body_hash": body_hash,
            "pr_number": pr_number,
            "source": source,
            "watcher_verdict": watcher_verdict,
            "original_body": original_body,
            "original_path": original_path,
            "original_line": original_line,
            "original_commit_sha": original_commit_sha,
        })
        if row is None:
            raise RuntimeError(
                "agent_runs row not found for review comment upsert: "
                f"{repository_full_name}#{github_issue_number}"
            )
        return ReviewCommentRecord.from_row(row)

    def mark_review_comment_handed_off(
        self,
        repository_full_name: str,
        github_issue_number: int,
        comment_key: str,
    ) -> ReviewCommentRecord:
        """Stamp ``handed_off_at`` the first time a comment is sent to the PM.

        Idempotent: the original hand-off timestamp is preserved so a later call
        does not look like a fresh hand-off.
        """
        validate_repository_full_name(repository_full_name)
        validate_issue_number(github_issue_number)
        validate_comment_key(comment_key)
        sql = f"""
            UPDATE review_comments AS rc
            SET handed_off_at = COALESCE(rc.handed_off_at, now())
            FROM agent_runs AS ar
            WHERE rc.agent_run_id = ar.run_id
              AND ar.repository_full_name = %(repository_full_name)s
              AND ar.github_issue_number = %(github_issue_number)s
              AND rc.comment_key = %(comment_key)s
            RETURNING {_review_comment_columns("rc")}
        """
        row = self._fetch_one(sql, {
            "repository_full_name": repository_full_name,
            "github_issue_number": github_issue_number,
            "comment_key": comment_key,
        })
        if row is None:
            raise RuntimeError(
                f"review_comments row {comment_key!r} not found for "
                f"{repository_full_name}#{github_issue_number}"
            )
        return ReviewCommentRecord.from_row(row)

    def record_review_comment_resolution(
        self,
        repository_full_name: str,
        github_issue_number: int,
        comment_key: str,
        *,
        resolution_status: str,
        pm_decision: str | None = None,
        addressed_by_commit_sha: str | None = None,
        verification_summary: str | None = None,
        verification_refs: Any = None,
    ) -> ReviewCommentRecord:
        """Persist the PM's decision for one review comment.

        ``addressed`` requires a commit sha and a verification summary;
        ``rejected`` / ``needs_user_judgment`` require a reason in
        ``verification_summary``. ``resolved_at`` is set for any terminal status
        and cleared for ``unresolved`` (the DB enforces the same invariants).
        """
        validate_repository_full_name(repository_full_name)
        validate_issue_number(github_issue_number)
        validate_comment_key(comment_key)
        validate_pm_decision(pm_decision)
        refs = validate_verification_refs(verification_refs)
        validate_review_comment_resolution(
            resolution_status,
            addressed_by_commit_sha=addressed_by_commit_sha,
            verification_summary=verification_summary,
        )
        sql = f"""
            UPDATE review_comments AS rc
            SET pm_decision = %(pm_decision)s,
                resolution_status = %(resolution_status)s,
                addressed_by_commit_sha = %(addressed_by_commit_sha)s,
                verification_summary = %(verification_summary)s,
                verification_refs = COALESCE(
                    %(verification_refs)s::jsonb, rc.verification_refs
                ),
                resolved_at = CASE
                    WHEN %(resolution_status)s = 'unresolved' THEN NULL
                    ELSE now()
                END
            FROM agent_runs AS ar
            WHERE rc.agent_run_id = ar.run_id
              AND ar.repository_full_name = %(repository_full_name)s
              AND ar.github_issue_number = %(github_issue_number)s
              AND rc.comment_key = %(comment_key)s
            RETURNING {_review_comment_columns("rc")}
        """
        row = self._fetch_one(sql, {
            "repository_full_name": repository_full_name,
            "github_issue_number": github_issue_number,
            "comment_key": comment_key,
            "pm_decision": pm_decision,
            "resolution_status": resolution_status,
            "addressed_by_commit_sha": addressed_by_commit_sha,
            "verification_summary": verification_summary,
            "verification_refs": (
                json.dumps(refs) if verification_refs is not None else None
            ),
        })
        if row is None:
            raise RuntimeError(
                f"review_comments row {comment_key!r} not found for "
                f"{repository_full_name}#{github_issue_number}"
            )
        return ReviewCommentRecord.from_row(row)

    def list_review_comments(
        self,
        repository_full_name: str,
        github_issue_number: int,
    ) -> list[ReviewCommentRecord]:
        validate_repository_full_name(repository_full_name)
        validate_issue_number(github_issue_number)
        sql = f"""
            SELECT {_review_comment_columns("rc")}
            FROM review_comments AS rc
            JOIN agent_runs AS ar ON ar.run_id = rc.agent_run_id
            WHERE ar.repository_full_name = %(repository_full_name)s
              AND ar.github_issue_number = %(github_issue_number)s
            ORDER BY rc.first_seen_at ASC
        """
        return [
            ReviewCommentRecord.from_row(r)
            for r in self._fetch_all(sql, {
                "repository_full_name": repository_full_name,
                "github_issue_number": github_issue_number,
            })
        ]

    def _validate_claim_payload(self, payload: ClaimPayload) -> None:
        validate_repository_full_name(payload.repository_full_name)
        validate_issue_number(payload.github_issue_number)
        validate_nonempty_nowhitespace(payload.parent_branch, "parent_branch")
        validate_nonempty_nowhitespace(payload.branch_name, "branch_name")
        validate_runner_identity_field(payload.runner_id, "runner_id")
        validate_runner_identity_field(payload.machine_id, "machine_id")
        validate_nonempty_nowhitespace(payload.locked_by, "locked_by")
        validate_worktree_basename(payload.worktree_basename)
        validate_nonempty_nowhitespace(payload.tmux_window, "tmux_window")
        validate_status(payload.status)
        if payload.review_result_relative_path != REVIEW_RESULT_RELATIVE_PATH:
            raise ValueError(
                "review_result_relative_path must be tmp/review-result.json"
            )

    def _fetch_one(self, sql: str, params: Mapping[str, Any]) -> Mapping[str, Any] | None:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        commit = getattr(self.conn, "commit", None)
        if commit is not None:
            commit()
        return row

    def _fetch_all(self, sql: str, params: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        # A bare SELECT opens a transaction in PostgreSQL; commit so the
        # connection does not linger 'idle in transaction' across loop passes
        # (mirrors `_fetch_one`).
        commit = getattr(self.conn, "commit", None)
        if commit is not None:
            commit()
        return rows

    def _require_row(self, sql: str, params: Mapping[str, Any]) -> AgentRun:
        row = self._fetch_one(sql, params)
        if row is None:
            raise RuntimeError("agent_runs row was not found")
        return AgentRun.from_row(row)
