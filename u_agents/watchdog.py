#!/usr/bin/env python3
"""v0.2 DB-backed watchdog for tmux PM agents.

Discovers active/stale PM runs through agent_runs, verifies external GitHub
and tmux reality, captures each PM pane, compares with stored hashes, pings
the pane if it is unchanged across several consecutive checks, and posts a
single GitHub issue comment if it is still unchanged after the ping.

The watchdog uses local JSON only for pane-stall counters.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from u_agents.agent_runs import ACTIVE_PHASES, AgentRun, AgentRunsClient, TERMINAL_PHASES
from u_agents.contract import (
    LABEL_IN_PROGRESS,
    LABEL_READY,
    RepoConfig,
    TMUX_SESSION,
    load_config,
    parse_window_name,
    pm_pane_target,
)

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_STATE_DIR = PACKAGE_DIR / "state"
DEFAULT_STATE_FILE = "watchdog.json"

PING_TEXT = (
    "You may be stalled. Please report current status, blocker, and next action."
)


@dataclass
class WindowState:
    last_hash: str = ""
    unchanged_checks: int = 0
    pinged: bool = False
    stall_comment_posted: bool = False
    last_update: float = 0.0


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def load_state(state_file: Path) -> Dict[str, WindowState]:
    if not state_file.exists():
        return {}
    try:
        text = state_file.read_text(encoding="utf-8")
        raw = json.loads(text) if text.strip() else {}
    except (json.JSONDecodeError, OSError) as e:
        print(
            f"WARN: watchdog state file {state_file} is unreadable ({e}); resetting to empty",
            file=sys.stderr,
        )
        return {}
    if not isinstance(raw, dict):
        print(
            f"WARN: watchdog state file {state_file} has invalid root schema; "
            f"resetting to empty",
            file=sys.stderr,
        )
        return {}

    allowed_fields = {f.name for f in fields(WindowState)}
    state: Dict[str, WindowState] = {}
    for k, v in raw.items():
        if not isinstance(v, dict):
            print(
                f"WARN: watchdog state entry {k!r} in {state_file} has invalid "
                f"schema; skipping",
                file=sys.stderr,
            )
            continue
        filtered = {name: value for name, value in v.items() if name in allowed_fields}
        try:
            state[k] = WindowState(**filtered)
        except TypeError as e:
            print(
                f"WARN: watchdog state entry {k!r} in {state_file} is invalid "
                f"({e}); skipping",
                file=sys.stderr,
            )
    return state


def save_state(state_file: Path, state: Dict[str, WindowState]) -> None:
    """Atomically persist state. Crash mid-write cannot corrupt state_file."""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {k: asdict(v) for k, v in state.items()}, indent=2, sort_keys=True,
    )
    fd, tmp_path = tempfile.mkstemp(
        prefix=state_file.name + ".",
        suffix=".tmp",
        dir=str(state_file.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp_path, state_file)
    except Exception:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise


# ---------------------------------------------------------------------------
# tmux + gh side-effects (overridable for tests)
# ---------------------------------------------------------------------------

def list_managed_windows() -> List[str]:
    res = subprocess.run(
        ["tmux", "list-windows", "-t", TMUX_SESSION, "-F", "#{window_name}"],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        return []
    out = []
    for w in res.stdout.splitlines():
        if parse_window_name(w):
            out.append(w)
    return out


def capture_pane(window: str) -> str:
    res = subprocess.run(
        ["tmux", "capture-pane", "-p", "-t", pm_pane_target(window)],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        return ""
    return res.stdout


def send_ping(window: str, dry_run: bool) -> bool:
    pane = pm_pane_target(window)
    if dry_run:
        print(f"DRY: ping {pane}", file=sys.stderr)
        return True
    # -l sends literal text without interpreting "Enter" etc.
    text_res = subprocess.run(
        ["tmux", "send-keys", "-t", pane, "-l", PING_TEXT],
        capture_output=True, text=True, check=False,
    )
    if text_res.returncode != 0:
        print(
            f"WARN: watchdog ping failed for {pane}: {text_res.stderr.strip()}",
            file=sys.stderr,
        )
        return False
    enter_res = subprocess.run(
        ["tmux", "send-keys", "-t", pane, "Enter"],
        capture_output=True, text=True, check=False,
    )
    if enter_res.returncode != 0:
        print(
            f"WARN: watchdog ping submit failed for {pane}: {enter_res.stderr.strip()}",
            file=sys.stderr,
        )
        return False
    return True


def build_stall_comment_body(
    window: str,
    capture: str,
    unchanged_checks: int,
    *,
    include_tail: bool = False,
) -> str:
    """Body for the GitHub stall comment.

    By default the body contains only safe metadata (tmux target, unchanged
    count, and a local inspection command). Pane content is not posted to
    GitHub by default because a PM pane can contain file contents, command
    output, API responses, local paths, or secrets that scrolled past the
    terminal during normal operation.

    Set include_tail=True to opt into posting the last 30 lines of the pane.
    When opted in, the tail is HTML-escaped inside a <pre> block to neutralize
    Markdown fence-injection from the captured content.
    """
    pane = pm_pane_target(window)
    lines = [
        f"PM watchdog: pane `{pane}` is unchanged after a ping. "
        f"Please check the agent.",
        "",
        f"unchanged-check count: {unchanged_checks}",
        "",
        "Inspect locally (pane content is intentionally not posted here):",
        "```sh",
        f"tmux attach -t {TMUX_SESSION} \\; select-window -t '{TMUX_SESSION}:{window}'",
        "```",
    ]
    if include_tail:
        tail = "\n".join(capture.splitlines()[-30:])
        # HTML-escape <, >, & so a captured Markdown code fence cannot break
        # out of the <pre> block.
        safe = (
            tail.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
        )
        lines += [
            "",
            "<details><summary>last pane tail (sensitive: may contain secrets, "
            "paths, or file contents from the PM pane)</summary>",
            "",
            "<pre>",
            safe,
            "</pre>",
            "</details>",
        ]
    return "\n".join(lines)


def post_stall_comment(
    repo_full: str,
    issue_number: int,
    window: str,
    capture: str,
    unchanged_checks: int,
    dry_run: bool,
    *,
    include_tail: bool = False,
) -> None:
    body = build_stall_comment_body(
        window, capture, unchanged_checks, include_tail=include_tail,
    )
    if dry_run:
        print(
            f"DRY: would comment stall on {repo_full}#{issue_number} "
            f"(include_tail={include_tail})",
            file=sys.stderr,
        )
        return
    res = subprocess.run(
        [
            "gh", "issue", "comment", str(issue_number),
            "--repo", repo_full, "--body", body,
        ],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        print(
            f"WARN: stall comment failed for {repo_full}#{issue_number}: "
            f"{res.stderr.strip()}",
            file=sys.stderr,
        )


# "could not resolve to" matches GitHub GraphQL missing-resource errors
# (e.g. "Could not resolve to an Issue ..."). It deliberately excludes
# transient DNS/network failures like "Could not resolve host: api.github.com".
_ISSUE_ABSENCE_MARKERS = ("not found", "could not resolve to", "404")


def github_issue_allows_watchdog_action(run: AgentRun) -> bool:
    """Verify GitHub issue reality before pinging or commenting on a DB row.

    Returns ``False`` for definitive non-actionable reality (issue not OPEN,
    not found, or missing the required label). Raises ``RuntimeError`` for
    transient/ambiguous CLI/API failures so the loop logs and retries instead
    of recording a false ``github_issue_verification_failed`` observation.
    """
    res = subprocess.run(
        [
            "gh", "issue", "view", str(run.github_issue_number),
            "--repo", run.repository_full_name,
            "--json", "state,labels",
        ],
        capture_output=True, text=True, check=False,
    )
    if res.returncode != 0:
        stderr = (res.stderr or "").strip()
        if any(marker in stderr.lower() for marker in _ISSUE_ABSENCE_MARKERS):
            print(
                f"WARN: cannot verify issue for {run.repository_full_name}#"
                f"{run.github_issue_number}: {stderr}",
                file=sys.stderr,
            )
            return False
        raise RuntimeError(
            f"cannot verify issue {run.repository_full_name}#"
            f"{run.github_issue_number} (exit {res.returncode}); "
            f"treating as transient: {stderr}"
        )
    try:
        data = json.loads(res.stdout)
    except json.JSONDecodeError as e:
        # Malformed CLI output is ambiguous, not proof the issue is gone.
        raise RuntimeError(
            f"malformed issue verification JSON for "
            f"{run.repository_full_name}#{run.github_issue_number}: {e}"
        ) from e
    if data.get("state") != "OPEN":
        return False
    labels = {str(label.get("name", "")) for label in data.get("labels", [])}
    if run.phase == "claimed":
        return LABEL_READY in labels or LABEL_IN_PROGRESS in labels
    return LABEL_IN_PROGRESS in labels


# ---------------------------------------------------------------------------
# Core check
# ---------------------------------------------------------------------------

def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def resolve_repo(window: str, repos: List[RepoConfig]) -> Optional[Tuple[RepoConfig, int]]:
    parsed = parse_window_name(window)
    if not parsed:
        return None
    short, num = parsed
    for r in repos:
        if r.short_name == short:
            return r, num
    return None


def _db_windows_for_check(
    runs: Iterable[AgentRun],
    repos: List[RepoConfig],
    live_windows: set[str],
    db_client,
) -> Tuple[List[str], Dict[str, Tuple[str, int]]]:
    configured_repos = {repo.full_name for repo in repos}
    windows: List[str] = []
    window_lookup: Dict[str, Tuple[str, int]] = {}
    for run in runs:
        if run.phase in TERMINAL_PHASES:
            continue
        if run.phase not in ACTIVE_PHASES:
            continue
        if run.repository_full_name not in configured_repos:
            db_client.record_observation(
                run.repository_full_name,
                run.github_issue_number,
                {
                    "watchdog": "repository_not_configured",
                    "repository_full_name": run.repository_full_name,
                },
            )
            print(
                f"WARN: DB row {run.repository_full_name}#"
                f"{run.github_issue_number} is not in watchdog config; "
                "skipping pane action",
                file=sys.stderr,
            )
            continue
        if run.tmux_window not in live_windows:
            db_client.record_observation(
                run.repository_full_name,
                run.github_issue_number,
                {
                    "watchdog": "tmux_window_missing",
                    "tmux_window": run.tmux_window,
                    "pm_pane": run.pm_pane,
                },
            )
            print(
                f"WARN: DB row {run.repository_full_name}#"
                f"{run.github_issue_number} points at missing tmux window "
                f"{run.tmux_window}; skipping pane action",
                file=sys.stderr,
            )
            continue
        if run.pm_pane is not None and run.pm_pane != pm_pane_target(run.tmux_window):
            db_client.record_observation(
                run.repository_full_name,
                run.github_issue_number,
                {
                    "watchdog": "pm_pane_mismatch",
                    "tmux_window": run.tmux_window,
                    "pm_pane": run.pm_pane,
                    "expected_pm_pane": pm_pane_target(run.tmux_window),
                },
            )
            print(
                f"WARN: DB row {run.repository_full_name}#"
                f"{run.github_issue_number} has pm_pane {run.pm_pane!r}; "
                f"expected {pm_pane_target(run.tmux_window)!r}; skipping pane action",
                file=sys.stderr,
            )
            continue
        windows.append(run.tmux_window)
        window_lookup[run.tmux_window] = (
            run.repository_full_name,
            run.github_issue_number,
        )
    return windows, window_lookup


def _runs_for_reconciliation(db_client) -> List[AgentRun]:
    runs_by_key: Dict[Tuple[str, int], AgentRun] = {}
    for run in db_client.list_active_runs():
        runs_by_key[(run.repository_full_name, run.github_issue_number)] = run
    for run in db_client.list_stale_runs():
        runs_by_key[(run.repository_full_name, run.github_issue_number)] = run
        db_client.record_observation(
            run.repository_full_name,
            run.github_issue_number,
            {
                "watchdog": "stale_lease",
                "lease_until": (
                    run.lease_until.isoformat()
                    if hasattr(run.lease_until, "isoformat")
                    else str(run.lease_until)
                ),
            },
        )
    return list(runs_by_key.values())


def check_once(
    repos: List[RepoConfig],
    state_file: Path,
    stall_checks: int,
    dry_run: bool,
    *,
    list_windows: Callable[[], List[str]] = list_managed_windows,
    capture: Callable[[str], str] = capture_pane,
    ping: Callable[[str, bool], bool] = send_ping,
    comment: Callable[[str, int, str, str, int, bool], None] = post_stall_comment,
    now: Callable[[], float] = time.time,
    db_client=None,
    verify_run: Callable[[AgentRun], bool] = github_issue_allows_watchdog_action,
) -> Dict[str, WindowState]:
    """Single check pass. Returns the updated in-memory state."""
    state = load_state(state_file)
    live_windows = list_windows()
    live_window_set = set(live_windows)
    db_window_lookup: Dict[str, Tuple[str, int]] = {}
    # Windows of runs deferred this pass by a transient verification failure.
    # Their stall state must survive the cleanup sweep below even though no
    # pane action runs for them, so a sustained outage cannot keep resetting
    # unchanged_checks / pinged / stall_comment_posted.
    deferred_windows: set[str] = set()
    if db_client is None:
        windows = live_windows
    else:
        candidate_runs = []
        for run in _runs_for_reconciliation(db_client):
            try:
                allowed = verify_run(run)
            except RuntimeError as e:
                # Transient/ambiguous verification failure: skip this run so the
                # outer loop retries next tick instead of polluting DB metadata.
                # If its tmux window is still live, preserve that window's stall
                # state through cleanup; a gone window is left out so genuinely
                # stale state can still expire normally.
                if run.tmux_window in live_window_set:
                    deferred_windows.add(run.tmux_window)
                print(
                    f"WARN: deferring watchdog action for "
                    f"{run.repository_full_name}#{run.github_issue_number}: {e}",
                    file=sys.stderr,
                )
                continue
            if allowed:
                candidate_runs.append(run)
                continue
            db_client.record_observation(
                run.repository_full_name,
                run.github_issue_number,
                {
                    "watchdog": "github_issue_verification_failed",
                    "phase": run.phase,
                },
            )
        windows, db_window_lookup = _db_windows_for_check(
            candidate_runs,
            repos,
            live_window_set,
            db_client,
        )
    # Seed `seen` with deferred live windows so the cleanup sweep keeps their
    # existing WindowState. They stay out of `windows`, so no capture / ping /
    # comment / counter update happens for them this pass.
    seen: set[str] = set(deferred_windows)

    for w in windows:
        seen.add(w)
        text = capture(w)
        h = _hash(text)
        st = state.get(w, WindowState())

        if h != st.last_hash:
            st = WindowState(last_hash=h, unchanged_checks=0, pinged=False,
                             stall_comment_posted=False, last_update=now())
        else:
            st.unchanged_checks += 1
            st.last_update = now()
            if st.unchanged_checks >= stall_checks and not st.pinged:
                try:
                    ping(w, dry_run)
                except Exception as e:
                    print(
                        f"WARN: watchdog ping raised for {pm_pane_target(w)}: "
                        f"{type(e).__name__}: {e}",
                        file=sys.stderr,
                    )
                st.pinged = True
            elif (
                st.pinged
                and st.unchanged_checks >= stall_checks * 2
                and not st.stall_comment_posted
            ):
                resolved = resolve_repo(w, repos)
                if w in db_window_lookup:
                    repo_full, num = db_window_lookup[w]
                    comment(repo_full, num, w, text, st.unchanged_checks, dry_run)
                    st.stall_comment_posted = True
                elif resolved is None:
                    print(
                        f"WARN: cannot resolve repo for window {w}; skipping stall comment",
                        file=sys.stderr,
                    )
                else:
                    repo, num = resolved
                    comment(repo.full_name, num, w, text, st.unchanged_checks, dry_run)
                    st.stall_comment_posted = True
        state[w] = st

    for w in list(state.keys()):
        if w not in seen:
            del state[w]

    save_state(state_file, state)
    return state


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _resolve_config(explicit: Optional[Path]) -> Path:
    # Delegate to launcher's resolution to keep config discovery in one place.
    from u_agents.launcher import find_config
    return find_config(explicit)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="v0.2 DB-backed PM pane watchdog")
    p.add_argument("--config", type=Path)
    p.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    p.add_argument("--interval", type=int, default=60,
                   help="seconds between checks (loop mode)")
    p.add_argument("--stall-checks", type=int, default=3,
                   help="consecutive unchanged checks before pinging")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--once", action="store_true",
                   help="run a single check pass and exit")
    p.add_argument(
        "--include-pane-tail",
        action="store_true",
        help=("opt in to embedding the last 30 lines of the PM pane in stall "
              "GitHub comments. SENSITIVE: pane output may contain secrets, "
              "file contents, paths, or API responses. Off by default."),
    )
    args = p.parse_args(argv)

    config_path = _resolve_config(args.config)
    repos = load_config(config_path)
    state_file = args.state_dir / DEFAULT_STATE_FILE
    db_client = AgentRunsClient.from_env()

    def comment_with_flag(repo_full, num, w, text, unchanged, dry):
        post_stall_comment(
            repo_full, num, w, text, unchanged, dry,
            include_tail=args.include_pane_tail,
        )

    def run_once():
        check_once(
            repos, state_file, args.stall_checks, args.dry_run,
            comment=comment_with_flag, db_client=db_client,
        )

    try:
        if args.once:
            run_once()
            return 0
        while True:
            try:
                run_once()
            except Exception as e:  # don't let one bad check kill the loop
                print(f"watchdog: {type(e).__name__}: {e}", file=sys.stderr)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0
    finally:
        db_client.close()


if __name__ == "__main__":
    raise SystemExit(main())
