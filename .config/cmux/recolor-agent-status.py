#!/usr/bin/env python3
"""Recolor cmux's built-in Claude Code sidebar status.

cmux hard-codes these colors (Running and Needs input share blue, Idle and
Waiting share gray), so a cmux automation (automations.json) runs this on each
claude_code set_status event and re-sends the same status with a per-state
color. The event JSON arrives in CMUX_AUTOMATION_EVENT_JSON.
"""
import json
import os
import shlex
import subprocess

# Keyed by icon, which identifies the state independently of the label text.
COLORS = {
    "point.3.filled.connected.trianglepath.dotted": "#BF5AF2",  # Running subagents
    "hourglass": "#FFD60A",  # Waiting on background work
    "bell.fill": "#FF9F0A",  # Needs input
    "pause.circle.fill": "#30D158",  # Idle: turn finished
}

CMUX = "/Applications/cmux.app/Contents/Resources/bin/cmux"


def parse(args):
    """Split set_status args into (key, value, flags); accepts --k=v and --k v."""
    tokens = shlex.split(args)
    i = 1
    while i < len(tokens) and not tokens[i].startswith("--"):
        i += 1
    key, value, flags = tokens[0], " ".join(tokens[1:i]), {}
    while i < len(tokens):
        name = tokens[i][2:]
        if "=" in name:
            name, flag_value = name.split("=", 1)
            flags[name] = flag_value
        elif i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
            i += 1
            flags[name] = tokens[i]
        else:
            flags[name] = ""
        i += 1
    return key, value, flags


def current_icon(workspace):
    out = subprocess.run(
        [CMUX, "list-status", "--workspace", workspace],
        capture_output=True, text=True,
    ).stdout
    for line in out.splitlines():
        if line.startswith("claude_code="):
            for part in line.split():
                if part.startswith("icon="):
                    return part[len("icon="):]
    return None


def main():
    event = json.loads(os.environ.get("CMUX_AUTOMATION_EVENT_JSON") or "{}")
    payload = event.get("payload") or {}
    if payload.get("command") != "set_status":
        return
    key, value, flags = parse(payload.get("args") or "")
    color = COLORS.get(flags.get("icon"))
    workspace = flags.pop("tab", None)
    if key != "claude_code" or not color or not workspace:
        return
    if flags.get("color", "").upper() == color:
        return
    # Skip a stale event: cmux may have moved to another state since.
    if current_icon(workspace) != flags["icon"]:
        return
    flags["color"] = color
    cmd = [CMUX, "set-status", key, value, "--workspace", workspace]
    for name, flag_value in flags.items():
        cmd += ["--" + name, flag_value]
    subprocess.run(cmd, capture_output=True)


if __name__ == "__main__":
    main()
