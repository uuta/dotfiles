#!/usr/bin/env python3
"""v0.1 Launcher: short-lived starter/resumer for tmux PM agents.

Picks one status:ready issue from an enabled target repository, claims it
by swapping labels and posting a claim comment, ensures a deterministic
tmux window exists, and sends the PM prompt into that window.

Read-only on GitHub by default; --dry-run additionally suppresses tmux
writes and claim mutations. GitHub authentication is required for issue
listing in both modes.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from u_agents.contract import (
    LABEL_IN_PROGRESS,
    LABEL_READY,
    RepoConfig,
    REVIEW_RESULT_STATUSES,
    TMUX_SESSION,
    branch_name,
    load_config,
    pm_pane_target,
    review_result_path,
    tmux_window_name,
    worktree_path,
)

PACKAGE_DIR = Path(__file__).resolve().parent

DEFAULT_CONFIG_PATHS = [
    PACKAGE_DIR / "config" / "repositories.yml",
    PACKAGE_DIR / "config" / "repositories.yaml",
    Path.home() / ".config" / "u-agents" / "repositories.yml",
    Path.home() / ".config" / "u-agents" / "repositories.yaml",
]

DEFAULT_PROMPT_TEMPLATE = PACKAGE_DIR / "prompts" / "pm.md"
CLAUDE_COMMAND = os.environ.get(
    "U_AGENTS_CLAUDE_COMMAND",
    "claude --permission-mode bypassPermissions",
)
CLAUDE_READY_TIMEOUT_SECONDS = 10.0
CLAUDE_READY_POLL_SECONDS = 0.25
CLAUDE_READY_SCAN_LINES = 40
CLAUDE_READY_RE = re.compile(r"^\s*(?:[│|]\s*)?[>❯]\s*(?:$|Try\b)")


@dataclass
class Issue:
    repo: RepoConfig
    number: int
    title: str
    url: str
    labels: List[str]


# ---------------------------------------------------------------------------
# Config discovery
# ---------------------------------------------------------------------------

def find_config(explicit: Optional[Path]) -> Path:
    if explicit is not None:
        if not explicit.exists():
            raise FileNotFoundError(f"Config not found: {explicit}")
        return explicit
    for p in DEFAULT_CONFIG_PATHS:
        if p.exists():
            return p
    raise FileNotFoundError(
        "No config found. Pass --config or create one at "
        + " or ".join(str(p) for p in DEFAULT_CONFIG_PATHS)
    )


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------

def _run(cmd: List[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def _list_by_label(repo: RepoConfig, label: str) -> List[Issue]:
    res = _run(
        [
            "gh", "issue", "list",
            "--repo", repo.full_name,
            "--label", label,
            "--state", "open",
            "--json", "number,title,url,labels",
            "--limit", "50",
        ]
    )
    if res.returncode != 0:
        msg = (res.stderr or "").strip()
        print(f"WARN: gh issue list failed for {repo.full_name}: {msg}", file=sys.stderr)
        return []
    if not res.stdout.strip():
        return []
    try:
        data = json.loads(res.stdout)
    except json.JSONDecodeError as e:
        print(
            f"WARN: gh issue list returned malformed JSON for "
            f"{repo.full_name}: {e}",
            file=sys.stderr,
        )
        return []
    out: List[Issue] = []
    for it in data:
        labels = [l.get("name", "") for l in it.get("labels", [])]
        out.append(
            Issue(
                repo=repo,
                number=int(it["number"]),
                title=str(it.get("title", "")),
                url=str(it.get("url", "")),
                labels=labels,
            )
        )
    return out


def list_ready_issues(repo: RepoConfig) -> List[Issue]:
    return _list_by_label(repo, LABEL_READY)


def list_in_progress_issues(repo: RepoConfig) -> List[Issue]:
    return _list_by_label(repo, LABEL_IN_PROGRESS)


def fetch_issue(repo: RepoConfig, number: int) -> Optional[Issue]:
    """Direct lookup of a specific issue regardless of label.

    Returns None if the issue cannot be fetched or is not OPEN.
    """
    res = _run(
        [
            "gh", "issue", "view", str(number),
            "--repo", repo.full_name,
            "--json", "number,title,url,labels,state",
        ]
    )
    if res.returncode != 0:
        print(
            f"WARN: gh issue view failed for {repo.full_name}#{number}: "
            f"{(res.stderr or '').strip()}",
            file=sys.stderr,
        )
        return None
    try:
        data = json.loads(res.stdout)
    except json.JSONDecodeError as e:
        print(
            f"WARN: gh issue view returned malformed JSON for "
            f"{repo.full_name}#{number}: {e}",
            file=sys.stderr,
        )
        return None
    state = data.get("state", "OPEN")
    if state != "OPEN":
        print(
            f"SKIP: {repo.full_name}#{number} is {state}; refusing to dispatch",
            file=sys.stderr,
        )
        return None
    labels = [l.get("name", "") for l in data.get("labels", [])]
    return Issue(
        repo=repo,
        number=int(data["number"]),
        title=str(data.get("title", "")),
        url=str(data.get("url", "")),
        labels=labels,
    )


def rollback_claim(issue: Issue, dry_run: bool) -> bool:
    """Revert a claim: status:in-progress -> status:ready.

    Used when dispatch fails after a successful label swap so the issue
    re-enters the queue. If this also fails, the resume path will recover
    the issue on the next launcher run.
    """
    if dry_run:
        print(
            f"DRY: would rollback labels to {LABEL_READY!r} on "
            f"{issue.repo.full_name}#{issue.number}",
            file=sys.stderr,
        )
        return True
    res = _run(
        [
            "gh", "issue", "edit", str(issue.number),
            "--repo", issue.repo.full_name,
            "--add-label", LABEL_READY,
            "--remove-label", LABEL_IN_PROGRESS,
        ]
    )
    if res.returncode != 0:
        print(
            f"WARN: label rollback failed for {issue.repo.full_name}#{issue.number}: "
            f"{(res.stderr or '').strip()}\n"
            f"      Recovery: re-run the launcher; the in-progress resume path will\n"
            f"      recreate the PM window. Or manually swap labels back.",
            file=sys.stderr,
        )
        return False
    return True


def claim_issue(issue: Issue, dry_run: bool) -> bool:
    """Swap status:ready -> status:in-progress.

    A failed claim is unsafe to dispatch because the issue may still be
    visible as status:ready to the next launcher run. Abort instead.
    """
    if dry_run:
        print(
            f"DRY: would add label {LABEL_IN_PROGRESS!r} and remove {LABEL_READY!r} "
            f"on {issue.repo.full_name}#{issue.number}",
            file=sys.stderr,
        )
        return True
    res = _run(
        [
            "gh", "issue", "edit", str(issue.number),
            "--repo", issue.repo.full_name,
            "--add-label", LABEL_IN_PROGRESS,
            "--remove-label", LABEL_READY,
        ]
    )
    if res.returncode != 0:
        stderr = (res.stderr or "").strip()
        lower = stderr.lower()
        if (
            "label not found" in lower
            or "not found" in lower and "label" in lower
            or "could not add" in lower and "label" in lower
        ):
            raise RuntimeError(
                f"label swap failed for {issue.repo.full_name}#{issue.number}: "
                f"{stderr}\n"
                f"Create the labels '{LABEL_READY}' and '{LABEL_IN_PROGRESS}' "
                f"on that repo, then re-run the launcher."
            )
        raise RuntimeError(
            f"gh issue edit failed for {issue.repo.full_name}#{issue.number}: {stderr}"
        )
    return True


def post_claim_comment(issue: Issue, window: str, dry_run: bool) -> None:
    body = (
        "Agent claim:\n"
        f"- tmux session: {TMUX_SESSION}\n"
        f"- tmux window: {window}\n"
        f"- pm pane: {pm_pane_target(window)}\n"
        f"- worktree: .worktrees/{issue.number}\n"
        f"- branch: {branch_name(issue.number)}\n"
        f"- pr: <empty until opened>\n"
    )
    if dry_run:
        print(
            f"DRY: would comment on {issue.repo.full_name}#{issue.number}:\n{body}",
            file=sys.stderr,
        )
        return
    res = _run(
        [
            "gh", "issue", "comment", str(issue.number),
            "--repo", issue.repo.full_name,
            "--body", body,
        ]
    )
    if res.returncode != 0:
        print(
            f"WARN: claim comment failed for {issue.repo.full_name}#{issue.number}: "
            f"{res.stderr.strip()}",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# tmux
# ---------------------------------------------------------------------------

def _tmux(args: List[str], check: bool = True) -> subprocess.CompletedProcess:
    return _run(["tmux", *args], check=check)


def ensure_session() -> None:
    res = _tmux(["has-session", "-t", TMUX_SESSION], check=False)
    if res.returncode != 0:
        _tmux(["new-session", "-d", "-s", TMUX_SESSION, "-n", "_init"])


def window_exists(window: str) -> bool:
    res = _tmux(
        ["list-windows", "-t", TMUX_SESSION, "-F", "#{window_name}"],
        check=False,
    )
    if res.returncode != 0:
        return False
    return window in res.stdout.splitlines()


def kill_window(window: str, dry_run: bool) -> bool:
    if dry_run:
        print(f"DRY: would kill tmux window {TMUX_SESSION}:{window}", file=sys.stderr)
        return True
    res = _tmux(["kill-window", "-t", f"{TMUX_SESSION}:{window}"], check=False)
    if res.returncode != 0:
        print(
            f"WARN: failed to kill tmux window {TMUX_SESSION}:{window}: "
            f"{(res.stderr or '').strip()}",
            file=sys.stderr,
        )
        return False
    return True


def ensure_window(repo: RepoConfig, issue: Issue, dry_run: bool) -> str:
    window = tmux_window_name(repo, issue.number)
    if dry_run:
        print(
            f"DRY: would ensure tmux window {window} running {CLAUDE_COMMAND!r}",
            file=sys.stderr,
        )
        return window
    ensure_session()
    if window_exists(window):
        wait_for_claude_ready(window)
        return window
    cwd = repo.main_checkout if Path(repo.main_checkout).is_dir() else repo.workspace_root
    if not Path(cwd).is_dir():
        cwd = str(Path.home())
    _tmux(["new-window", "-t", TMUX_SESSION, "-n", window, "-c", cwd, CLAUDE_COMMAND])
    _tmux(["select-pane", "-T", "pm", "-t", pm_pane_target(window)], check=False)
    wait_for_claude_ready(window)
    return window


def _command_name(command: str) -> str:
    command = command.strip()
    if len(command) >= 2 and command[0] == command[-1] and command[0] in ("'", '"'):
        command = command[1:-1]
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.split()
    if not parts:
        return ""
    return Path(parts[0]).name


def _is_expected_claude_start(command: str) -> bool:
    return _command_name(command) == _command_name(CLAUDE_COMMAND)


def _pane_start_command(window: str) -> Optional[str]:
    res = _tmux(
        ["display-message", "-p", "-t", pm_pane_target(window), "#{pane_start_command}"],
        check=False,
    )
    if res.returncode != 0:
        return None
    return res.stdout.strip()


def _pane_is_dead(window: str) -> bool:
    res = _tmux(
        ["display-message", "-p", "-t", pm_pane_target(window), "#{pane_dead}"],
        check=False,
    )
    if res.returncode != 0:
        return True
    return res.stdout.strip() == "1"


def _capture_pane(window: str) -> str:
    res = _tmux(["capture-pane", "-p", "-t", pm_pane_target(window)], check=False)
    if res.returncode != 0:
        return ""
    return res.stdout


def _claude_appears_ready(capture: str) -> bool:
    return any(
        CLAUDE_READY_RE.search(line)
        for line in capture.splitlines()[-CLAUDE_READY_SCAN_LINES:]
    )


def wait_for_claude_ready(window: str) -> None:
    """Verify prompt delivery would target an idle Claude Code prompt."""
    deadline = time.monotonic() + CLAUDE_READY_TIMEOUT_SECONDS
    last_start: Optional[str] = None
    saw_claude_process = False
    while time.monotonic() < deadline:
        start = _pane_start_command(window)
        dead = _pane_is_dead(window)
        if start is not None:
            last_start = start
            if _is_expected_claude_start(start) and not dead:
                saw_claude_process = True
                if _claude_appears_ready(_capture_pane(window)):
                    return
            elif start and not _is_expected_claude_start(start):
                raise RuntimeError(
                    f"tmux pane {pm_pane_target(window)} was started by "
                    f"{start!r}, not {CLAUDE_COMMAND!r}; refusing to send PM prompt"
                )
            elif dead:
                raise RuntimeError(
                    f"tmux pane {pm_pane_target(window)} is dead; "
                    f"refusing to send PM prompt"
                )
        time.sleep(CLAUDE_READY_POLL_SECONDS)
    if saw_claude_process:
        raise RuntimeError(
            f"Claude Code pane {pm_pane_target(window)} did not show an idle "
            f"input prompt before timeout; refusing to send PM prompt"
        )
    detail = "<missing pane>" if last_start is None else repr(last_start)
    raise RuntimeError(
        f"tmux pane {pm_pane_target(window)} is not a ready Claude Code pane "
        f"(start command: {detail}); refusing to send PM prompt"
    )


def send_prompt(window: str, prompt: str, dry_run: bool) -> None:
    pane = pm_pane_target(window)
    if dry_run:
        print(f"DRY: would send prompt to {pane}:\n----\n{prompt}\n----",
              file=sys.stderr)
        return
    wait_for_claude_ready(window)
    buf = f"u-agent-prompt-{os.getpid()}"
    _tmux_in(["tmux", "load-buffer", "-b", buf, "-"], prompt)
    try:
        _tmux(["paste-buffer", "-b", buf, "-t", pane])
        time.sleep(0.5)
        _tmux(["send-keys", "-t", pane, "C-m"])
    finally:
        _tmux(["delete-buffer", "-b", buf], check=False)


def _tmux_in(cmd: List[str], data: str) -> None:
    res = subprocess.run(cmd, input=data, text=True, capture_output=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed: {res.stderr.strip()}")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def pick_issue(
    repos: List[RepoConfig],
    target_repo: Optional[str],
    target_issue: Optional[int],
    list_fn: Optional[Callable[[RepoConfig], List[Issue]]] = None,
) -> Optional[Issue]:
    # Late-bound so monkey-patching list_ready_issues at the module level is honored.
    if list_fn is None:
        list_fn = list_ready_issues
    for repo in repos:
        if not repo.enabled:
            continue
        if target_repo and repo.full_name != target_repo and repo.short_name != target_repo:
            continue
        for issue in list_fn(repo):
            if target_issue is None or issue.number == target_issue:
                return issue
    return None


_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def render_pm_prompt(template_path: Path, issue: Issue, window: str) -> str:
    repo = issue.repo
    mapping = {
        "repo_full": repo.full_name,
        "repo_short": repo.short_name,
        "workspace_root": repo.workspace_root,
        "default_branch": repo.default_branch,
        "main_checkout": repo.main_checkout,
        "worktrees_root": repo.worktrees_root,
        "worktree": worktree_path(repo, issue.number),
        "review_result": review_result_path(repo, issue.number),
        "review_result_statuses": ", ".join(REVIEW_RESULT_STATUSES),
        "branch": branch_name(issue.number),
        "issue_number": str(issue.number),
        "issue_title": issue.title,
        "issue_url": issue.url,
        "tmux_session": TMUX_SESSION,
        "tmux_window": window,
        "pm_pane": pm_pane_target(window),
    }
    tmpl = template_path.read_text(encoding="utf-8")

    def repl(m: re.Match) -> str:
        key = m.group(1)
        if key not in mapping:
            raise KeyError(f"Unknown placeholder {{{key}}} in {template_path}")
        return mapping[key]

    return _PLACEHOLDER_RE.sub(repl, tmpl)


def classify_direct_issue(issue: Issue) -> str:
    """Pure decision for direct-lookup (--issue + --repo) mode.

    Returns 'claim' when status:ready, 'resume' when status:in-progress,
    'skip' otherwise.
    """
    if LABEL_READY in issue.labels:
        return "claim"
    if LABEL_IN_PROGRESS in issue.labels:
        return "resume"
    return "skip"


def select_resume_targets(
    repos: List[RepoConfig],
    target_repo: Optional[str] = None,
    target_issue: Optional[int] = None,
    *,
    list_in_progress_fn: Optional[Callable[[RepoConfig], List[Issue]]] = None,
    window_exists_fn: Optional[Callable[[str], bool]] = None,
) -> List[Issue]:
    """In-progress issues whose deterministic PM window is missing.

    Applies the same target_repo / target_issue filters as pick_issue so a
    general run with --repo or --issue cannot resume unrelated work. Pass
    None to leave the corresponding axis unfiltered.

    Side-effects only through the injected helpers, so the planner is
    testable without invoking tmux or gh. Late-bound defaults so that
    monkey-patching list_in_progress_issues / window_exists at the module
    level (as tests do) is honored.
    """
    if list_in_progress_fn is None:
        list_in_progress_fn = list_in_progress_issues
    if window_exists_fn is None:
        window_exists_fn = window_exists
    out: List[Issue] = []
    for repo in repos:
        if not repo.enabled:
            continue
        if target_repo and repo.full_name != target_repo and repo.short_name != target_repo:
            continue
        for issue in list_in_progress_fn(repo):
            if target_issue is not None and issue.number != target_issue:
                continue
            if not window_exists_fn(tmux_window_name(repo, issue.number)):
                out.append(issue)
    return out


def _resolve_repo(repos: List[RepoConfig], name: str) -> Optional[RepoConfig]:
    for r in repos:
        if r.full_name == name or r.short_name == name:
            return r
    return None


def dispatch_claim(issue: Issue, args) -> int:
    """Full claim flow with partial-claim rollback.

    Order: label swap -> ensure window -> claim comment -> send prompt.
    If anything after the swap raises, attempt to revert the label so the
    issue re-enters the queue. The resume sweep recovers it next run if
    the rollback itself fails.
    """
    repo = issue.repo
    window = tmux_window_name(repo, issue.number)
    window_preexisted = False

    if not args.dry_run and window_exists(window):
        window_preexisted = True
        print(
            f"SKIP: deterministic window {window} already exists for "
            f"{repo.full_name}#{issue.number}; refusing to dispatch a duplicate PM.\n"
            f"      Attach with: tmux attach -t {TMUX_SESSION}\n"
            f"      If the existing PM is dead: tmux kill-window -t {TMUX_SESSION}:{window}",
            file=sys.stderr,
        )
        return 0

    print(
        f"Claiming {repo.full_name}#{issue.number} \"{issue.title}\"",
        file=sys.stderr,
    )
    try:
        swapped = claim_issue(issue, args.dry_run)
    except RuntimeError as e:
        print(
            f"ERROR: claim failed for {repo.full_name}#{issue.number}: {e}\n"
            f"       Aborting dispatch before tmux work.",
            file=sys.stderr,
        )
        return 2
    if not swapped:
        print(
            f"ERROR: claim failed for {repo.full_name}#{issue.number}; "
            f"aborting dispatch before tmux work",
            file=sys.stderr,
        )
        return 2
    try:
        ensure_window(repo, issue, args.dry_run)
        post_claim_comment(issue, window, args.dry_run)
        prompt = render_pm_prompt(args.prompt_template, issue, window)
        send_prompt(window, prompt, args.dry_run)
    except Exception as e:
        if swapped:
            print(
                f"ERROR: dispatch failed after claim "
                f"({type(e).__name__}: {e}).\n"
                f"       Attempting label rollback for {repo.full_name}#{issue.number}",
                file=sys.stderr,
            )
            rollback_claim(issue, args.dry_run)
            if not args.dry_run and not window_preexisted and window_exists(window):
                print(
                    f"       Cleaning up newly created tmux window "
                    f"{TMUX_SESSION}:{window}",
                    file=sys.stderr,
                )
                kill_window(window, args.dry_run)
        else:
            print(
                f"ERROR: dispatch failed: {type(e).__name__}: {e}",
                file=sys.stderr,
            )
        raise
    print(
        f"OK: dispatched PM for {repo.full_name}#{issue.number} "
        f"-> {pm_pane_target(window)}",
        file=sys.stderr,
    )
    return 0


def dispatch_resume(issue: Issue, args) -> int:
    """Re-attach a PM window for an already-claimed (status:in-progress) issue.

    No label change. No claim comment. If the deterministic window is
    already alive, this is a no-op.
    """
    repo = issue.repo
    window = tmux_window_name(repo, issue.number)

    if not args.dry_run and window_exists(window):
        print(
            f"SKIP: PM window {window} already running for "
            f"{repo.full_name}#{issue.number}; nothing to resume",
            file=sys.stderr,
        )
        return 0

    print(f"Resuming {repo.full_name}#{issue.number} -> {window}", file=sys.stderr)
    try:
        ensure_window(repo, issue, args.dry_run)
        prompt = render_pm_prompt(args.prompt_template, issue, window)
        send_prompt(window, prompt, args.dry_run)
    except Exception as e:
        print(
            f"ERROR: resume failed for {repo.full_name}#{issue.number}: "
            f"{type(e).__name__}: {e}",
            file=sys.stderr,
        )
        raise
    print(
        f"OK: resumed PM for {repo.full_name}#{issue.number} "
        f"-> {pm_pane_target(window)}",
        file=sys.stderr,
    )
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="v0.1 Launcher for tmux PM agents")
    p.add_argument("--config", type=Path, help="repositories config path (yaml or json)")
    p.add_argument("--dry-run", action="store_true",
                   help="do not mutate GitHub or tmux; print intended actions")
    p.add_argument("--repo", help="restrict to a single repo (short or full name)")
    p.add_argument("--issue", type=int, help="restrict to a specific issue number")
    p.add_argument("--prompt-template", type=Path, default=DEFAULT_PROMPT_TEMPLATE)
    args = p.parse_args(argv)

    config_path = find_config(args.config)
    repos = load_config(config_path)

    # Direct-lookup mode: --issue + --repo act on that exact issue regardless
    # of queue position. Supports both fresh claim and resume of an
    # already-claimed issue.
    if args.issue is not None and args.repo is not None:
        repo = _resolve_repo(repos, args.repo)
        if repo is None:
            print(f"ERROR: repo '{args.repo}' is not in {config_path}", file=sys.stderr)
            return 2
        issue = fetch_issue(repo, args.issue)
        if issue is None:
            return 2
        kind = classify_direct_issue(issue)
        if kind == "claim":
            return dispatch_claim(issue, args)
        if kind == "resume":
            return dispatch_resume(issue, args)
        print(
            f"SKIP: {repo.full_name}#{issue.number} has neither "
            f"'{LABEL_READY}' nor '{LABEL_IN_PROGRESS}'; refusing to dispatch",
            file=sys.stderr,
        )
        return 0

    # General run:
    #   1) resume any in-progress issues whose PM window is missing
    #   2) claim one new status:ready issue
    # --repo / --issue restrict both phases so a filtered general run does
    # not touch unrelated repos or issues.
    resume_targets = select_resume_targets(
        repos, target_repo=args.repo, target_issue=args.issue,
    )
    for issue in resume_targets:
        try:
            dispatch_resume(issue, args)
        except Exception:
            # already logged; keep sweeping other resume targets
            pass

    issue = pick_issue(repos, args.repo, args.issue)
    if issue is None:
        if not resume_targets:
            print("No status:ready issue found.", file=sys.stderr)
        return 0
    return dispatch_claim(issue, args)


if __name__ == "__main__":
    raise SystemExit(main())
