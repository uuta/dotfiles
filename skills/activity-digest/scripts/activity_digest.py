#!/usr/bin/env python3

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


HOME = Path.home()
LOCAL_TZ = datetime.now().astimezone().tzinfo or ZoneInfo("Asia/Tokyo")
IGNORE_CWD_PREFIXES = [
    HOME / ".claude",
    HOME / ".codex",
]


def run(cmd, cwd=None):
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return 127, "", f"command not found: {cmd[0]}"


def parse_args():
    parser = argparse.ArgumentParser(description="Generate an activity digest from local logs.")
    parser.add_argument("--date", default=datetime.now(LOCAL_TZ).date().isoformat())
    parser.add_argument("--repo", action="append", default=[], help="Repository path to include.")
    return parser.parse_args()


def parse_timestamp(value):
    if not value:
        return None
    value = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(value).astimezone(LOCAL_TZ)
    except ValueError:
        return None


def same_local_date(ts, target_date):
    parsed = parse_timestamp(ts)
    return parsed is not None and parsed.date().isoformat() == target_date


def shorten(text, limit=100):
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def extract_text_from_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if text:
                chunks.append(text)
        return "\n".join(chunks)
    return ""


def resolve_git_root(path):
    code, out, _ = run(["git", "-C", str(path), "rev-parse", "--show-toplevel"])
    if code == 0 and out:
        return Path(out)
    return None


def normalize_path(path_str):
    try:
        return Path(path_str).expanduser().resolve()
    except OSError:
        return Path(path_str).expanduser()


def should_ignore_cwd(path_str):
    if not path_str:
        return False
    try:
        path = Path(path_str).resolve()
    except OSError:
        return False
    for prefix in IGNORE_CWD_PREFIXES:
        try:
            path.relative_to(prefix.resolve())
            return True
        except ValueError:
            continue
    return False


def parse_github_slug(url):
    if not url:
        return None
    match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    if not match:
        return None
    return match.group(1)


def get_gh_login():
    code, out, _ = run(["gh", "api", "user", "-q", ".login"])
    if code == 0 and out:
        return out.strip()
    return None


def collect_codex_activity(target_date):
    root = HOME / ".codex" / "sessions"
    yyyy, mm, dd = target_date.split("-")
    session_dir = root / yyyy / mm / dd
    activities = []
    if not session_dir.exists():
        return activities

    for path in sorted(session_dir.glob("*.jsonl")):
        activity = {
            "path": path,
            "cwd": None,
            "turns_started": 0,
            "turns_completed": 0,
            "user_messages": [],
        }
        try:
            with path.open() as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    obj_type = obj.get("type")
                    payload = obj.get("payload", {})

                    if obj_type == "session_meta":
                        activity["cwd"] = payload.get("cwd") or activity["cwd"]
                    elif obj_type == "turn_context":
                        activity["cwd"] = payload.get("cwd") or activity["cwd"]
                    elif obj_type == "event_msg":
                        event_type = payload.get("type")
                        if event_type == "task_started":
                            activity["turns_started"] += 1
                        elif event_type == "task_complete":
                            activity["turns_completed"] += 1
                        elif event_type == "user_message":
                            msg = payload.get("message")
                            if msg:
                                activity["user_messages"].append(shorten(msg, 120))
                    elif obj_type == "response_item":
                        if payload.get("type") != "message" or payload.get("role") != "user":
                            continue
                        text = extract_text_from_content(payload.get("content"))
                        if text:
                            activity["user_messages"].append(shorten(text, 120))
        except (OSError, json.JSONDecodeError):
            continue

        deduped = []
        seen = set()
        for message in activity["user_messages"]:
            if not message or message in seen:
                continue
            seen.add(message)
            deduped.append(message)
        activity["user_messages"] = deduped[:5]
        activities.append(activity)
    return activities


def collect_claude_activity(target_date):
    root = HOME / ".claude" / "projects"
    activities = []
    if not root.exists():
        return activities

    for project_dir in sorted(root.iterdir()):
        if not project_dir.is_dir():
            continue
        for path in sorted(project_dir.glob("*.jsonl")):
            try:
                modified = datetime.fromtimestamp(path.stat().st_mtime, LOCAL_TZ).date().isoformat()
            except OSError:
                continue
            if modified != target_date:
                continue

            activity = {
                "path": path,
                "cwd": None,
                "user_messages": [],
                "assistant_messages": 0,
            }
            matched = False
            try:
                with path.open() as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        obj = json.loads(line)
                        ts = obj.get("timestamp")
                        if ts and not same_local_date(ts, target_date):
                            continue
                        cwd = obj.get("cwd")
                        if cwd:
                            activity["cwd"] = cwd
                        obj_type = obj.get("type")
                        if obj_type == "user":
                            matched = True
                            message = obj.get("message", {})
                            content = extract_text_from_content(message.get("content"))
                            if content:
                                activity["user_messages"].append(shorten(content, 120))
                        elif obj_type == "assistant":
                            matched = True
                            activity["assistant_messages"] += 1
            except (OSError, json.JSONDecodeError):
                continue

            if not matched:
                continue
            deduped = []
            seen = set()
            for message in activity["user_messages"]:
                if not message or message in seen:
                    continue
                seen.add(message)
                deduped.append(message)
            activity["user_messages"] = deduped[:5]
            activities.append(activity)
    return activities


def collect_shell_snapshots(target_date):
    root = HOME / ".codex" / "shell_snapshots"
    snapshots = []
    if not root.exists():
        return snapshots
    for path in sorted(root.glob("*.sh")):
        try:
            modified = datetime.fromtimestamp(path.stat().st_mtime, LOCAL_TZ).date().isoformat()
        except OSError:
            continue
        if modified == target_date:
            snapshots.append(path)
    return snapshots


def collect_tmux_activity(target_date):
    today = datetime.now(LOCAL_TZ).date().isoformat()
    if target_date != today:
        return {
            "available": False,
            "reason": "tmux current state is only reliable for the current local date",
            "panes": [],
        }

    code, out, err = run(
        [
            "tmux",
            "list-panes",
            "-a",
            "-F",
            "#{session_name}\t#{window_index}\t#{pane_index}\t#{pane_active}\t#{pane_current_command}\t#{pane_current_path}\t#{pane_title}",
        ]
    )
    if code != 0:
        reason = err or "tmux unavailable"
        return {
            "available": False,
            "reason": reason,
            "panes": [],
        }

    panes = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 6)
        if len(parts) != 7:
            continue
        session_name, window_index, pane_index, pane_active, command, cwd, title = parts
        if should_ignore_cwd(cwd):
            continue
        panes.append(
            {
                "session_name": session_name,
                "window_index": window_index,
                "pane_index": pane_index,
                "active": pane_active == "1",
                "command": command or "",
                "cwd": cwd or "",
                "title": title or "",
            }
        )
    return {
        "available": True,
        "reason": "",
        "panes": panes,
    }


def collect_observed_targets(explicit_repos, codex_activities, claude_activities, tmux_activity):
    targets = {}

    def ensure_target(path_str):
        if not path_str:
            return None
        normalized = normalize_path(path_str)
        if should_ignore_cwd(str(normalized)):
            return None
        key = str(normalized)
        if key not in targets:
            repo_root = resolve_git_root(normalized)
            targets[key] = {
                "path": normalized,
                "repo_root": repo_root,
                "kind": "git" if repo_root else "directory",
                "sources": set(),
                "codex_sessions": 0,
                "claude_sessions": 0,
                "tmux_panes": 0,
            }
        return targets[key]

    for repo in explicit_repos:
        entry = ensure_target(repo)
        if entry:
            entry["sources"].add("explicit")

    cwd_root = resolve_git_root(Path.cwd())
    if cwd_root:
        entry = ensure_target(str(cwd_root))
        if entry:
            entry["sources"].add("current_cwd")

    for activity in codex_activities:
        cwd = activity.get("cwd")
        if not cwd:
            continue
        entry = ensure_target(cwd)
        if entry:
            entry["sources"].add("codex")
            entry["codex_sessions"] += 1

    for activity in claude_activities:
        cwd = activity.get("cwd")
        if not cwd:
            continue
        entry = ensure_target(cwd)
        if entry:
            entry["sources"].add("claude")
            entry["claude_sessions"] += 1

    for pane in tmux_activity.get("panes", []):
        cwd = pane.get("cwd")
        if not cwd:
            continue
        entry = ensure_target(cwd)
        if entry:
            entry["sources"].add("tmux")
            entry["tmux_panes"] += 1

    result = []
    for entry in targets.values():
        entry["sources"] = sorted(entry["sources"])
        result.append(entry)
    return sorted(result, key=lambda item: str(item["path"]))


def collect_repo_paths(observed_targets):
    repo_paths = set()
    for target in observed_targets:
        repo_root = target.get("repo_root")
        if repo_root:
            repo_paths.add(repo_root)
    return sorted(repo_paths)


def git_summary(repo, target_date, gh_login, observed_paths):
    summary = {
        "path": repo,
        "branch": "",
        "status": [],
        "commits": [],
        "reflog": [],
        "slug": None,
        "issues": [],
        "prs": [],
        "observed_paths": observed_paths,
    }
    code, branch, _ = run(["git", "-C", str(repo), "branch", "--show-current"])
    if code == 0:
        summary["branch"] = branch

    code, status, _ = run(["git", "-C", str(repo), "status", "--short"])
    if code == 0 and status:
        summary["status"] = status.splitlines()[:20]

    code, commits, _ = run(
        [
            "git",
            "-C",
            str(repo),
            "log",
            "--since",
            f"{target_date} 00:00",
            "--until",
            f"{target_date} 23:59:59",
            "--pretty=format:%h %s",
        ]
    )
    if code == 0 and commits:
        summary["commits"] = commits.splitlines()[:10]

    code, reflog, _ = run(
        [
            "git",
            "-C",
            str(repo),
            "reflog",
            "--since",
            f"{target_date} 00:00",
            "--until",
            f"{target_date} 23:59:59",
            "--date=iso-local",
            "--pretty=format:%h %gs",
        ]
    )
    if code == 0 and reflog:
        summary["reflog"] = reflog.splitlines()[:10]

    code, remote_url, _ = run(["git", "-C", str(repo), "remote", "get-url", "origin"])
    if code == 0:
        summary["slug"] = parse_github_slug(remote_url)

    if summary["slug"] and gh_login:
        issue_cmd = [
            "gh",
            "issue",
            "list",
            "--repo",
            summary["slug"],
            "--state",
            "all",
            "--limit",
            "5",
            "--search",
            f"updated:{target_date} author:{gh_login}",
            "--json",
            "number,title,state,url,updatedAt",
        ]
        code, issue_json, _ = run(issue_cmd)
        if code == 0 and issue_json:
            try:
                summary["issues"] = json.loads(issue_json)
            except json.JSONDecodeError:
                pass

        pr_cmd = [
            "gh",
            "pr",
            "list",
            "--repo",
            summary["slug"],
            "--state",
            "all",
            "--limit",
            "5",
            "--search",
            f"updated:{target_date} author:{gh_login}",
            "--json",
            "number,title,state,url,updatedAt",
        ]
        code, pr_json, _ = run(pr_cmd)
        if code == 0 and pr_json:
            try:
                summary["prs"] = json.loads(pr_json)
            except json.JSONDecodeError:
                pass

    return summary


def group_activity(activities):
    grouped = defaultdict(lambda: {"count": 0, "turns": 0, "completed": 0, "assistant_messages": 0, "messages": []})
    for activity in activities:
        key = activity.get("cwd") or "(unknown cwd)"
        if key != "(unknown cwd)" and should_ignore_cwd(key):
            continue
        entry = grouped[key]
        entry["count"] += 1
        entry["turns"] += activity.get("turns_started", 0)
        entry["completed"] += activity.get("turns_completed", 0)
        entry["assistant_messages"] += activity.get("assistant_messages", 0)
        entry["messages"].extend(activity.get("user_messages", []))

    result = []
    for cwd, data in grouped.items():
        deduped = []
        seen = set()
        for message in data["messages"]:
            if message in seen:
                continue
            seen.add(message)
            deduped.append(message)
        data["messages"] = deduped[:5]
        result.append((cwd, data))
    return sorted(result, key=lambda item: item[0])


def render(observed_targets, repo_summaries, codex_groups, claude_groups, tmux_activity, snapshots, target_date):
    lines = []
    lines.append(f"# Activity Digest - {target_date}")
    lines.append("")
    lines.append("## Overview")
    lines.append(f"- observed targets: {len(observed_targets)}")
    lines.append(f"- repositories: {len(repo_summaries)}")
    lines.append(f"- codex session groups: {len(codex_groups)}")
    lines.append(f"- claude activity groups: {len(claude_groups)}")
    lines.append(f"- tmux panes: {len(tmux_activity.get('panes', []))}")
    lines.append(f"- shell snapshots: {len(snapshots)}")
    lines.append("")

    lines.append("## Observed Targets")
    if not observed_targets:
        lines.append("- none")
    for target in observed_targets:
        lines.append(f"### {target['path']}")
        lines.append(f"- kind: {target['kind']}")
        if target["repo_root"]:
            lines.append(f"- repo root: {target['repo_root']}")
        lines.append(f"- sources: {', '.join(target['sources'])}")
        if target["codex_sessions"]:
            lines.append(f"- codex sessions: {target['codex_sessions']}")
        if target["claude_sessions"]:
            lines.append(f"- claude sessions: {target['claude_sessions']}")
        if target["tmux_panes"]:
            lines.append(f"- tmux panes: {target['tmux_panes']}")
        lines.append("")

    lines.append("## Repositories")
    if not repo_summaries:
        lines.append("- none")
    for repo in repo_summaries:
        slug = f" ({repo['slug']})" if repo["slug"] else ""
        lines.append(f"### {repo['path']}{slug}")
        lines.append(f"- branch: {repo['branch'] or '(unknown)'}")
        if repo["observed_paths"]:
            lines.append("- observed paths:")
            for observed in repo["observed_paths"]:
                lines.append(f"  - {observed['path']} [{', '.join(observed['sources'])}]")
        if repo["commits"]:
            lines.append("- commits:")
            for commit in repo["commits"]:
                lines.append(f"  - {commit}")
        else:
            lines.append("- commits: none")
        if repo["reflog"]:
            lines.append("- reflog:")
            for item in repo["reflog"][:10]:
                lines.append(f"  - {item}")
        if repo["status"]:
            lines.append("- working tree:")
            for item in repo["status"][:10]:
                lines.append(f"  - {item}")
        else:
            lines.append("- working tree: clean")
        if repo["issues"]:
            lines.append("- issues updated:")
            for issue in repo["issues"]:
                lines.append(f"  - #{issue['number']} [{issue['state']}] {issue['title']}")
        if repo["prs"]:
            lines.append("- prs updated:")
            for pr in repo["prs"]:
                lines.append(f"  - #{pr['number']} [{pr['state']}] {pr['title']}")
        lines.append("")

    lines.append("## Codex Activity")
    if not codex_groups:
        lines.append("- none")
    for cwd, data in codex_groups:
        lines.append(f"### {cwd}")
        lines.append(f"- sessions: {data['count']}")
        if data["turns"]:
            lines.append(f"- turns started: {data['turns']}")
        if data["completed"]:
            lines.append(f"- turns completed: {data['completed']}")
        if data["messages"]:
            lines.append("- user asks:")
            for message in data["messages"]:
                lines.append(f"  - {message}")
        lines.append("")

    lines.append("## Claude Activity")
    if not claude_groups:
        lines.append("- none")
    for cwd, data in claude_groups:
        lines.append(f"### {cwd}")
        lines.append(f"- sessions: {data['count']}")
        if data["assistant_messages"]:
            lines.append(f"- assistant messages: {data['assistant_messages']}")
        if data["messages"]:
            lines.append("- user asks:")
            for message in data["messages"]:
                lines.append(f"  - {message}")
        lines.append("")

    lines.append("## Tmux Activity")
    if not tmux_activity.get("available"):
        lines.append(f"- unavailable: {tmux_activity.get('reason') or 'unknown'}")
    elif not tmux_activity.get("panes"):
        lines.append("- none")
    else:
        for pane in tmux_activity["panes"]:
            pane_ref = f"{pane['session_name']}:{pane['window_index']}.{pane['pane_index']}"
            lines.append(f"### {pane_ref}")
            lines.append(f"- cwd: {pane['cwd'] or '(unknown)'}")
            lines.append(f"- command: {pane['command'] or '(unknown)'}")
            lines.append(f"- active: {'yes' if pane['active'] else 'no'}")
            if pane["title"]:
                lines.append(f"- title: {pane['title']}")
            lines.append("")

    lines.append("## Shell Snapshots")
    if snapshots:
        lines.append(f"- count: {len(snapshots)}")
        for path in snapshots[-5:]:
            lines.append(f"  - {path.name}")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def main():
    args = parse_args()
    target_date = args.date
    gh_login = get_gh_login()

    codex_activities = collect_codex_activity(target_date)
    claude_activities = collect_claude_activity(target_date)
    tmux_activity = collect_tmux_activity(target_date)
    snapshots = collect_shell_snapshots(target_date)
    observed_targets = collect_observed_targets(args.repo, codex_activities, claude_activities, tmux_activity)
    repo_paths = collect_repo_paths(observed_targets)
    observed_by_repo = defaultdict(list)
    for target in observed_targets:
        repo_root = target.get("repo_root")
        if repo_root:
            observed_by_repo[repo_root].append(
                {
                    "path": str(target["path"]),
                    "kind": target["kind"],
                    "sources": target["sources"],
                    "codex_sessions": target["codex_sessions"],
                    "claude_sessions": target["claude_sessions"],
                    "tmux_panes": target["tmux_panes"],
                }
            )
    repo_summaries = [
        git_summary(repo, target_date, gh_login, observed_by_repo.get(repo, []))
        for repo in repo_paths
    ]
    codex_groups = group_activity(codex_activities)
    claude_groups = group_activity(claude_activities)

    print(render(observed_targets, repo_summaries, codex_groups, claude_groups, tmux_activity, snapshots, target_date))


if __name__ == "__main__":
    sys.exit(main())
