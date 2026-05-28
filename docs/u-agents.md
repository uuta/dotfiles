# v0.1 local agent runner

Small local runner around tmux + git + `gh` for the workflow described in
[#5](https://github.com/uuta/u/issues/5). GitHub Issues / PRs / CI are the
source of truth. There is no ops DB, no daemon, no vector store.

## Components

| Component  | Path                          | Role                                                                 |
| ---------- | ----------------------------- | -------------------------------------------------------------------- |
| Contract   | `u_agents/contract.py`          | Config types and deterministic tmux/worktree/branch naming.          |
| Launcher   | `u_agents/launcher.py`          | Short-lived starter/resumer. Picks one ready issue and hands off PM. |
| PM prompt  | `u_agents/prompts/pm.md`        | The contract sent into the PM pane. PM owns the per-issue workflow.  |
| Watchdog   | `u_agents/watchdog.py`          | Detects stalled PM panes. Pings, then comments once if still stuck.  |
| Config     | `config/repositories.yml`     | Local allowlist of repositories the Launcher may operate on.         |

## Required tools

- `python3` (>= 3.10)
- `tmux`
- `gh` (authenticated against the target repositories)
- `claude` (Claude Code CLI; override with `U_AGENTS_CLAUDE_COMMAND` if needed)
- `git`
- `yq` (MikeFarah; only needed for YAML configs — `.json` configs do not require it)

## Configuration

Copy the example and edit:

```sh
mkdir -p ~/.config/u-agents
cp config/repositories.example.yml ~/.config/u-agents/repositories.yml
```

Or keep the config in-repo at `config/repositories.yml` and pass `--config` explicitly.

Discovery order when `--config` is omitted:

1. `./config/repositories.yml`
2. `./config/repositories.yaml`
3. `~/.config/u-agents/repositories.yml`
4. `~/.config/u-agents/repositories.yaml`

Each entry:

| Field            | Meaning                                                                  |
| ---------------- | ------------------------------------------------------------------------ |
| `full_name`      | GitHub `owner/name`.                                                     |
| `workspace_root` | Absolute local path. Main checkout = `${workspace_root}/${default_branch}`. Worktrees = `${workspace_root}/.worktrees`. |
| `default_branch` | Base branch for PRs and main checkout location.                          |
| `enabled`        | If false, Launcher skips this repo.                                      |

## Required GitHub labels

The Launcher swaps these labels when claiming an issue. Create them on each
enabled repo:

- `status:ready` — issue is ready for an agent to claim.
- `status:in-progress` — set by the Launcher when it claims an issue.

If the labels do not exist, the Launcher aborts before creating a tmux
window. Add the labels and re-run to enable proper queue semantics.

Optional but recommended sizing labels: `size:s`, `size:m`, `size:l`.

## Naming contract

| Item             | Rule                                                       |
| ---------------- | ---------------------------------------------------------- |
| tmux session     | `agents`                                                   |
| issue window     | `<repo-short>-<issue-number>` (e.g. `trander-flutter-233`) |
| PM pane          | `agents:<window>.0` (pane title `pm`)                      |
| worktree         | `${workspace_root}/.worktrees/<issue-number>`              |
| branch           | `feat/<issue-number>`                                      |

These names are deterministic. Both Launcher and Watchdog reconstruct them
from `(repo, issue_number)` — no shared state file needed.

## Commands

### Launcher

```sh
# general run: resume any in-progress issue whose PM window is missing,
# then claim one new status:ready issue
python3 -m u_agents.launcher

# direct lookup: act on this exact issue regardless of queue position.
# - if status:ready  -> full claim + dispatch
# - if status:in-progress -> resume (no label change, no claim comment)
# - otherwise -> skip
python3 -m u_agents.launcher --repo trander-flutter --issue 233

# inspect what would happen without touching GitHub or tmux
python3 -m u_agents.launcher --dry-run

# alternate config path
python3 -m u_agents.launcher --config ~/my-repos.yml
```

`--dry-run` suppresses all writes (label swap, claim comment, tmux window
creation, prompt send) but still reads issue state from GitHub.

#### Resume and partial-claim recovery

Every general run first scans `status:in-progress` issues across enabled
repos. For each whose deterministic tmux window is missing, the Launcher
re-creates the window and re-sends the PM prompt. No label change happens
during resume. Issues whose PM window is already alive are left alone (no
duplicate dispatch).

If `dispatch_claim` fails after the label swap (tmux unavailable, prompt
send error, etc.), the Launcher attempts to roll the labels back to
`status:ready` and cleans up any tmux window newly created by that failed
handoff. If even the rollback fails, the next run's resume sweep re-creates
the missing PM window from the `status:in-progress` state. Either way, no
issue is silently stranded.

Direct-lookup mode (`--issue N --repo R`) bypasses the queue and supports
both fresh claim and resume of an already-claimed issue.

### Watchdog

```sh
# single check pass and exit (useful from cron)
python3 -m u_agents.watchdog --once

# loop, checking every 60s
python3 -m u_agents.watchdog --interval 60

# tune stall threshold (default: 3 consecutive unchanged checks before ping)
python3 -m u_agents.watchdog --interval 30 --stall-checks 4

# dry-run skips ping send and GitHub comment, still writes state file
python3 -m u_agents.watchdog --once --dry-run

# OPT-IN: include the last 30 lines of the PM pane in the GitHub stall
# comment. OFF BY DEFAULT because pane output can contain secrets,
# credentials, file contents, paths, or API responses that scrolled through
# the terminal. Enable only when you trust the repo's collaborator audience.
python3 -m u_agents.watchdog --once --include-pane-tail
```

Default stall-comment body contains only safe metadata: tmux target, the
unchanged-check count, and a `tmux attach` command for local inspection.
Pane content is never posted unless `--include-pane-tail` is set; when set,
the tail is HTML-escaped inside a `<pre>` block to neutralize Markdown
fence-injection from captured output.

State is persisted to `${XDG_STATE_HOME:-~/.local/state}/u-agents/watchdog.json`
via an atomic `tempfile + os.replace` write, so a crash mid-write cannot
corrupt the file. If the state file does become unreadable (manual edit,
disk truncation), `load_state` warns and resets to empty instead of
deadlocking the watchdog loop.

Stalled-once-and-commented windows do not get re-commented until their pane
output changes.

Suggested cron entry (single check per minute):

```cron
* * * * * /usr/bin/env python3 -m u_agents.watchdog --once >> ~/Library/Logs/u-agents-watchdog.log 2>&1
```

## Scheduling under launchd (macOS)

On macOS, prefer `launchd` over `cron`. Two example plists are tracked in
`examples/launchd/`:

| File | Job | Interval | Notes |
| ---- | --- | -------- | ----- |
| `local.u-agents.launcher.plist` | `u_agents.launcher` | 300 s (5 min) | One pass: resume sweep + claim one ready issue. |
| `local.u-agents.watchdog.plist` | `u_agents.watchdog --once` | 60 s (1 min) | One check pass; launchd owns the cadence. |

### Before installing

1. **Dry-run first**, on the command line, exactly as launchd will run it.
   Catch missing config, missing labels, or wrong python path while you can
   read the error directly:

   ```sh
   /opt/homebrew/bin/python3 -m u_agents.launcher \
     --config /Users/your-name/.config/u-agents/repositories.yml --dry-run

   /opt/homebrew/bin/python3 -m u_agents.watchdog \
     --config /Users/your-name/.config/u-agents/repositories.yml --once --dry-run
   ```

2. Edit the four placeholder paths in each plist:
   - `/opt/homebrew/bin/python3` — your python interpreter
   - `/Users/your-name/.config/u-agents/repositories.yml` — your config
   - `/Users/your-name/dotfiles` — the dotfiles checkout (must contain `u_agents/`)
   - `/Users/your-name/Library/Logs/u-agents-*.log` — log destination

3. Make sure `PATH` in the plist includes the directories holding `gh`,
   `tmux`, `git`, and `yq`. The examples set `/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin`.

### Install / start / stop / uninstall

```sh
# Install (copies to ~/Library/LaunchAgents and registers)
cp examples/launchd/local.u-agents.launcher.plist ~/Library/LaunchAgents/
cp examples/launchd/local.u-agents.watchdog.plist ~/Library/LaunchAgents/
launchctl load   ~/Library/LaunchAgents/local.u-agents.launcher.plist
launchctl load   ~/Library/LaunchAgents/local.u-agents.watchdog.plist

# Trigger one run immediately (otherwise wait for the next interval tick)
launchctl start  local.u-agents.launcher
launchctl start  local.u-agents.watchdog

# Stop the most recent in-flight run (does NOT unload the schedule)
launchctl stop   local.u-agents.watchdog

# Inspect schedule and exit codes
launchctl list | grep u-agents

# Tail the logs
tail -F ~/Library/Logs/u-agents-launcher.log \
        ~/Library/Logs/u-agents-watchdog.log

# Uninstall (unregister and remove)
launchctl unload ~/Library/LaunchAgents/local.u-agents.launcher.plist
launchctl unload ~/Library/LaunchAgents/local.u-agents.watchdog.plist
rm ~/Library/LaunchAgents/local.u-agents.launcher.plist
rm ~/Library/LaunchAgents/local.u-agents.watchdog.plist
```

### Why watchdog uses `--once`

The watchdog also has a long-loop form (`--interval 60` without `--once`),
but under launchd you want `--once` so:

- Every tick is a fresh process; if the python process ever hangs or
  exhausts memory, launchd will simply launch a new one next interval.
- launchd surfaces exit codes per run (via `launchctl list`) which is more
  useful than a single long-lived process whose internal loop is opaque.
- Combining a python sleep loop with launchd duplicates the scheduler.

For the same reason, the launcher plist uses launchd's `StartInterval`
rather than a sleep loop in python.

### Suggested intervals

| Job | Interval | Rationale |
| --- | -------- | --------- |
| launcher | 300 s | New ready issues are rare; resume sweep is cheap but not free (one `gh issue list` per enabled repo). |
| watchdog | 60 s | Combined with default `--stall-checks=3`, a pane must be unchanged for ~3 minutes before a ping and another ~3 minutes after a ping before a stall comment. Decrease for tighter detection, increase to save API quota. |

## Workflow

```
GitHub issue with status:ready
        │
        ▼
   Launcher picks one
        │
        ├─ swaps status:ready -> status:in-progress
        ├─ posts claim comment with tmux/worktree/branch coords
        ├─ ensures `agents:<window>` exists
        └─ sends PM prompt into the window
                │
                ▼
        PM (tmux pane)
                │
                ├─ creates/reuses worktree + branch
                ├─ organizes requirements from the issue
                ├─ engineer pane implements
                ├─ reviewer pane runs review-diff
                ├─ fix loop bounded to 3 rounds
                └─ opens review-ready PR with `Closes #N`

        Watchdog (separate loop)
                │
                ├─ capture-pane → hash → compare
                ├─ N unchanged checks → tmux send-keys ping
                └─ 2N unchanged after ping → one issue comment, then quiet
```

## What this v0.1 deliberately does not do

- No Postgres / Redis / Temporal / message queues.
- No long-running daemon.
- No semantic memory / vector DB.
- No multi-machine locking. Single-Launcher single-machine assumption.
- No PR / CI / merged status labels — those are reconstructed from GitHub.
- No automatic worktree cleanup. Cleanup happens manually after PR merge.

## Verification

```sh
python3 -m unittest discover tests
python3 -m u_agents.launcher --help
python3 -m u_agents.watchdog --help
python3 -m u_agents.watchdog --once --dry-run   # works without any active tmux windows
```

A live Launcher dry-run requires `gh auth login` against the configured
repositories.
