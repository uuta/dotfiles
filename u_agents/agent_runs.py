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
    AGENT_RUN_PHASES,
    RunnerIdentity,
    database_url_from_env,
    load_runner_identity,
    validate_identity_value,
    validate_worktree_basename,
)


ACTIVE_PHASES = (
    "claimed",
    "pm_started",
    "engineering",
    "reviewing",
    "fixing",
    "pr_open",
    "pr_watching",
    "ready_to_merge",
)
TERMINAL_PHASES = ("blocked", "done", "cancelled")

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

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "AgentRun":
        return cls(
            repository_full_name=str(row["repository_full_name"]),
            github_issue_number=int(row["github_issue_number"]),
            parent_branch=str(row["parent_branch"]),
            branch_name=str(row["branch_name"]),
            phase=str(row["phase"]),
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


def validate_phase(value: str) -> str:
    if value not in AGENT_RUN_PHASES:
        raise ValueError(f"phase must be one of: {', '.join(AGENT_RUN_PHASES)}")
    return value


def validate_metadata(metadata: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if metadata is None:
        return {}
    if not isinstance(metadata, Mapping):
        raise ValueError("metadata must be a mapping/object")
    json.dumps(dict(metadata))
    return metadata


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
        "phase, runner_id, machine_id, locked_by, lease_until, "
        "worktree_basename, tmux_window, pm_pane, pr_number, "
        "pr_review_fix_rounds, block_reason, metadata"
    )


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
                branch_name, phase, runner_id, machine_id, locked_by,
                lease_until, worktree_basename, tmux_window,
                review_result_relative_path, metadata
            ) VALUES (
                %(repository_full_name)s, %(github_issue_number)s,
                %(parent_branch)s, %(branch_name)s, %(phase)s,
                %(runner_id)s, %(machine_id)s, %(locked_by)s,
                %(lease_until)s, %(worktree_basename)s, %(tmux_window)s,
                %(review_result_relative_path)s, '{{}}'::jsonb
            )
            ON CONFLICT (repository_full_name, github_issue_number) DO UPDATE
            SET parent_branch = EXCLUDED.parent_branch,
                branch_name = EXCLUDED.branch_name,
                phase = 'claimed',
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
               OR agent_runs.phase IN ('blocked', 'done', 'cancelled')
            RETURNING {_row_columns()}
        """
        row = self._fetch_one(sql, payload.__dict__)
        if row is None:
            raise RuntimeError(
                "agent_runs claim lease is held by another runner for "
                f"{payload.repository_full_name}#{payload.github_issue_number}"
            )
        return AgentRun.from_row(row)

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
        validate_repository_full_name(repository_full_name)
        validate_issue_number(github_issue_number)
        validate_phase(phase)
        validate_metadata(metadata)
        if phase == "blocked" and (block_reason is None or block_reason.strip() == ""):
            raise ValueError("block_reason is required when phase is blocked")
        sql = f"""
            UPDATE agent_runs
            SET phase = %(phase)s,
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
            "phase": phase,
            "block_reason": block_reason,
            "clear_lease": clear_lease,
            "metadata": json.dumps(dict(metadata or {})),
        })

    def update_tmux_coordinates(
        self,
        repository_full_name: str,
        github_issue_number: int,
        *,
        tmux_window: str,
        pm_pane: str | None,
        phase: str = "pm_started",
    ) -> AgentRun:
        validate_repository_full_name(repository_full_name)
        validate_issue_number(github_issue_number)
        validate_nonempty_nowhitespace(tmux_window, "tmux_window")
        if pm_pane is not None:
            validate_nonempty_nowhitespace(pm_pane, "pm_pane")
        validate_phase(phase)
        sql = f"""
            UPDATE agent_runs
            SET phase = %(phase)s,
                tmux_window = %(tmux_window)s,
                pm_pane = %(pm_pane)s
            WHERE repository_full_name = %(repository_full_name)s
              AND github_issue_number = %(github_issue_number)s
            RETURNING {_row_columns()}
        """
        return self._require_row(sql, {
            "repository_full_name": repository_full_name,
            "github_issue_number": github_issue_number,
            "phase": phase,
            "tmux_window": tmux_window,
            "pm_pane": pm_pane,
        })

    def mark_pm_started(self, run: AgentRun) -> AgentRun:
        return self.update_tmux_coordinates(
            run.repository_full_name,
            run.github_issue_number,
            tmux_window=run.tmux_window,
            pm_pane=pm_pane_target(run.tmux_window),
            phase="pm_started",
        )

    def update_pr_fields(
        self,
        repository_full_name: str,
        github_issue_number: int,
        *,
        pr_number: int | None = None,
        phase: str | None = None,
        increment_fix_rounds: bool = False,
        block_reason: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> AgentRun:
        validate_repository_full_name(repository_full_name)
        validate_issue_number(github_issue_number)
        if pr_number is not None and pr_number <= 0:
            raise ValueError("pr_number must be positive when set")
        if phase is not None:
            validate_phase(phase)
        validate_metadata(metadata)
        if phase == "blocked" and (block_reason is None or block_reason.strip() == ""):
            raise ValueError("block_reason is required when phase is blocked")
        sql = f"""
            UPDATE agent_runs
            SET pr_number = COALESCE(%(pr_number)s, pr_number),
                phase = COALESCE(%(phase)s, phase),
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
            "phase": phase,
            "increment_fix_rounds": increment_fix_rounds,
            "block_reason": block_reason,
            "metadata": json.dumps(dict(metadata or {})),
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

        Sets ``phase = 'pr_open'`` and ``pr_number`` so the PR watcher's
        ``list_pr_watch_runs`` query (phase in pr_open/pr_watching/ready_to_merge
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
            phase="pr_open",
            metadata=observation,
        )

    def record_observation(
        self,
        repository_full_name: str,
        github_issue_number: int,
        observation: Mapping[str, Any],
    ) -> AgentRun:
        return self.update_phase(
            repository_full_name,
            github_issue_number,
            phase=self.get_run(repository_full_name, github_issue_number).phase,
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
            WHERE phase = ANY(%(phases)s)
            ORDER BY updated_at ASC
        """
        return [AgentRun.from_row(r) for r in self._fetch_all(sql, {"phases": list(ACTIVE_PHASES)})]

    def list_stale_runs(self) -> list[AgentRun]:
        sql = f"""
            SELECT {_row_columns()}
            FROM agent_runs
            WHERE phase = ANY(%(phases)s)
              AND lease_until IS NOT NULL
              AND lease_until < now()
            ORDER BY lease_until ASC
        """
        return [AgentRun.from_row(r) for r in self._fetch_all(sql, {"phases": list(ACTIVE_PHASES)})]

    def list_pr_watch_runs(self) -> list[AgentRun]:
        sql = f"""
            SELECT {_row_columns()}
            FROM agent_runs
            WHERE phase IN ('pr_open', 'pr_watching', 'ready_to_merge')
              AND pr_number IS NOT NULL
            ORDER BY updated_at ASC
        """
        return [AgentRun.from_row(r) for r in self._fetch_all(sql, {})]

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
        validate_phase(payload.phase)
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
