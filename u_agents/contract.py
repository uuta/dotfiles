"""Shared types and naming contract for the v0.1 agent runner.

Naming is deterministic so Launcher and Watchdog reconstruct the same names
from a (repo, issue_number) pair without needing an ops DB.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List


TMUX_SESSION = "agents"
LABEL_READY = "status:ready"
LABEL_IN_PROGRESS = "status:in-progress"
REVIEW_RESULT_RELATIVE_PATH = "tmp/review-result.json"
REVIEW_RESULT_STATUSES = ("running", "clean", "fix_required", "blocked")

_WINDOW_RE = re.compile(r"^(?P<repo>[A-Za-z0-9._-]+)-(?P<num>\d+)$")


@dataclass(frozen=True)
class RepoConfig:
    full_name: str
    workspace_root: str
    default_branch: str
    enabled: bool = True

    @property
    def short_name(self) -> str:
        return self.full_name.split("/", 1)[-1]

    @property
    def main_checkout(self) -> str:
        return f"{self.workspace_root.rstrip('/')}/{self.default_branch}"

    @property
    def worktrees_root(self) -> str:
        return f"{self.workspace_root.rstrip('/')}/.worktrees"


class ConfigError(ValueError):
    pass


def load_config(path: Path) -> List[RepoConfig]:
    """Load a repositories config (YAML via external yq, or JSON)."""
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in (".yml", ".yaml"):
        data = _yaml_to_dict(text, path)
    elif suffix == ".json":
        data = json.loads(text)
    else:
        raise ConfigError(f"Unsupported config extension: {path.suffix}")

    repos_raw = data.get("repositories") if isinstance(data, dict) else None
    if not isinstance(repos_raw, list):
        raise ConfigError(f"Config missing 'repositories' list: {path}")

    out: List[RepoConfig] = []
    for i, r in enumerate(repos_raw):
        if not isinstance(r, dict):
            raise ConfigError(f"repositories[{i}] must be a mapping")
        for field in ("full_name", "workspace_root", "default_branch"):
            if field not in r:
                raise ConfigError(f"repositories[{i}] missing required field: {field}")
        out.append(
            RepoConfig(
                full_name=str(r["full_name"]),
                workspace_root=str(r["workspace_root"]),
                default_branch=str(r["default_branch"]),
                enabled=bool(r.get("enabled", True)),
            )
        )
    return out


def _yaml_to_dict(text: str, path: Path) -> dict:
    if shutil.which("yq") is None:
        raise ConfigError(
            "yq is required to parse YAML config; install MikeFarah yq or use a .json config"
        )
    res = subprocess.run(
        ["yq", "-o=json", "."],
        input=text,
        text=True,
        capture_output=True,
        check=False,
    )
    if res.returncode != 0:
        raise ConfigError(f"yq failed for {path}: {res.stderr.strip()}")
    return json.loads(res.stdout or "{}")


# Naming helpers -----------------------------------------------------------

def tmux_window_name(repo: RepoConfig, issue_number: int) -> str:
    return f"{repo.short_name}-{issue_number}"


def pm_pane_target(window: str) -> str:
    return f"{TMUX_SESSION}:{window}.0"


def branch_name(issue_number: int) -> str:
    return f"feat/{issue_number}"


def worktree_path(repo: RepoConfig, issue_number: int) -> str:
    return f"{repo.worktrees_root}/{issue_number}"


def review_result_path(repo: RepoConfig, issue_number: int) -> str:
    return f"{worktree_path(repo, issue_number)}/{REVIEW_RESULT_RELATIVE_PATH}"


def parse_window_name(window: str) -> tuple[str, int] | None:
    """Parse a deterministic window name back into (repo_short, issue_number)."""
    m = _WINDOW_RE.match(window)
    if not m:
        return None
    return m.group("repo"), int(m.group("num"))
