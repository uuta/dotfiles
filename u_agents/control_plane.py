"""Pure v0.2 control-plane contract helpers.

This module intentionally avoids opening a database connection. It keeps
runner identity validation and phase-transition decisions unit-testable while
the SQL schema remains the source of truth for persisted state.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse

from u_agents.contract import ConfigError


AGENT_RUN_PHASES = (
    "claimed",
    "pm_started",
    "engineering",
    "reviewing",
    "fixing",
    "pr_open",
    "pr_watching",
    "ready_to_merge",
    "blocked",
    "done",
    "cancelled",
)

PR_REVIEW_FIX_MAX_ROUNDS = 1
ENV_DATABASE_URL = "U_AGENTS_DATABASE_URL"
ENV_RUNNER_ID = "U_AGENTS_RUNNER_ID"
ENV_MACHINE_ID = "U_AGENTS_MACHINE_ID"
_PLACEHOLDER_IDENTITIES = {
    "runner",
    "runner-id",
    "runner_id",
    "machine",
    "machine-id",
    "machine_id",
    "placeholder",
    "changeme",
    "change-me",
    "todo",
    "example",
}


@dataclass(frozen=True)
class RunnerIdentity:
    runner_id: str
    machine_id: str

    @property
    def lock_owner(self) -> str:
        return f"{self.runner_id}@{self.machine_id}"


@dataclass(frozen=True)
class PrWatchDecision:
    phase: str
    increment_fix_rounds: bool = False
    block_reason: str = ""


def _require_env(env: Mapping[str, object], name: str) -> str:
    value = env.get(name, "")
    if not isinstance(value, str) or value.strip() == "":
        raise ConfigError(f"{name} is required and must be non-empty")
    return value


def validate_identity_value(value: str, name: str) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise ConfigError(f"{name} is required and must be non-empty")
    if value.strip().lower() in _PLACEHOLDER_IDENTITIES:
        raise ConfigError(f"{name} must not be a placeholder identity")
    return value


def database_url_from_env(env: Mapping[str, object] | None = None) -> str:
    """Read and validate the PostgreSQL connection URL from environment."""
    url = _require_env(os.environ if env is None else env, ENV_DATABASE_URL)
    if urlparse(url).scheme not in ("postgresql", "postgres"):
        raise ConfigError(
            f"{ENV_DATABASE_URL} must use postgresql:// or postgres://"
        )
    return url


def load_runner_identity(env: Mapping[str, object] | None = None) -> RunnerIdentity:
    """Read runner identity from environment.

    Agents must not invent these values. The caller must provide them via
    process environment or an equivalent configuration layer.
    """
    source = os.environ if env is None else env
    return RunnerIdentity(
        runner_id=validate_identity_value(
            _require_env(source, ENV_RUNNER_ID), ENV_RUNNER_ID,
        ),
        machine_id=validate_identity_value(
            _require_env(source, ENV_MACHINE_ID), ENV_MACHINE_ID,
        ),
    )


def validate_worktree_basename(value: str) -> str:
    """Validate the DB worktree_basename rule in Python."""
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError("worktree_basename must be non-empty")
    if any(ch.isspace() for ch in value):
        raise ValueError("worktree_basename must not contain whitespace")
    if value in (".", "..") or "/" in value or "\\" in value:
        raise ValueError("worktree_basename must be a basename only")
    return value


def decide_pr_watch_phase(
    *,
    pr_merged: bool,
    ci_green: bool,
    must_fix_review_comments: bool,
    pr_review_fix_rounds: int,
) -> PrWatchDecision:
    """Return the next phase for a PR watcher observation.

    Automated PR review comment fixes are allowed at most once. This function
    models only the decision rule; callers still need to verify GitHub PR,
    CI, and review-comment reality before applying the returned transition.
    """
    if pr_review_fix_rounds < 0:
        raise ValueError("pr_review_fix_rounds must be >= 0")
    if pr_merged:
        return PrWatchDecision(phase="done")
    if must_fix_review_comments:
        if pr_review_fix_rounds < PR_REVIEW_FIX_MAX_ROUNDS:
            return PrWatchDecision(phase="fixing", increment_fix_rounds=True)
        return PrWatchDecision(
            phase="blocked",
            block_reason=(
                "PR review has must-fix comments after the automated fix "
                "round limit"
            ),
        )
    if ci_green:
        return PrWatchDecision(phase="ready_to_merge")
    return PrWatchDecision(phase="pr_watching")
