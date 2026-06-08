# v0.2 DB-backed local agent runner

Small local runner around tmux + git + `gh` for the workflow described in
[#5](https://github.com/uuta/u/issues/5). GitHub Issues / PRs / CI, tmux,
git worktrees, and `tmp/review-result.json` remain the external realities.
PostgreSQL `agent_runs` coordinates claimed work across runner processes.

## Components

| Component  | Path                          | Role                                                                 |
| ---------- | ----------------------------- | -------------------------------------------------------------------- |
| Contract   | `u_agents/contract.py`          | Config types and deterministic tmux/worktree/branch naming.          |
| Control plane helpers | `u_agents/control_plane.py` | v0.2 pure phase/env decision helpers.                      |
| Launcher   | `u_agents/launcher.py`          | Short-lived starter/resumer. Picks one ready issue and hands off PM. |
| PM prompt  | `u_agents/prompts/pm.md`        | The contract sent into the PM pane. PM owns the per-issue workflow.  |
| Watchdog   | `u_agents/watchdog.py`          | Detects stalled PM panes. Pings, then comments once if still stuck.  |
| PR Watcher | `u_agents/pr_watcher.py`        | Watches verified PR state and updates PR phases in `agent_runs`.     |
| PR-open CLI | `u_agents/mark_pr_open.py`      | PM-run helper that durably sets `phase=pr_open` + `pr_number` after a PR is opened. |
| DB schema   | `u_agents/db/001_agent_runs.sql` | v0.2 PostgreSQL schema for claimed runs.                         |
| DB docs     | `u_agents/db/README.md`         | Column ownership, phase contract, and PR watcher rules.             |
| Config     | `u_agents/config/repositories.yml` | Local allowlist of repositories the Launcher may operate on.     |
| State      | `<dotfiles checkout>/u_agents/state/watchdog.json` | Local Watchdog runtime state.                       |

## Required tools

- `python3` (>= 3.10)
- `tmux`
- `gh` (authenticated against the target repositories)
- `claude` (Claude Code CLI; Launcher starts it with
  `--permission-mode bypassPermissions` by default. Override with
  `U_AGENTS_CLAUDE_COMMAND` if needed.)
- `git`
- `yq` (MikeFarah; only needed for YAML configs — `.json` configs do not require it)
- Docker, for the local PostgreSQL control plane.
- `psycopg` for live DB runtime connections. The import is lazy, so unit tests
  and `--help` paths still work without it:

  ```sh
  python3 -m pip install 'psycopg[binary]'
  ```

## Configuration

Copy the example and edit:

```sh
mkdir -p u_agents/config
cp u_agents/config/repositories.example.yml u_agents/config/repositories.yml
```

The local config file is intentionally ignored by git. The tracked example
stays in `u_agents/config/repositories.example.yml`.

Discovery order when `--config` is omitted:

1. `<u_agents package>/config/repositories.yml`
2. `<u_agents package>/config/repositories.yaml`
3. `~/.config/u-agents/repositories.yml`
4. `~/.config/u-agents/repositories.yaml`

The first two paths are anchored to the installed `u_agents` package
directory (next to `launcher.py`), not the process working directory, so
discovery works regardless of where the launcher is run from. The
`~/.config/u-agents/` paths are compatibility fallbacks. New installs
should use the `u_agents/config/` path inside the dotfiles checkout.

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

## mise-managed target repos

Some target repos (and their per-issue worktrees) carry a `mise.toml`,
`.mise.toml`, or `.config/mise/config.toml`. An untrusted mise config makes
`mise run` / `mise exec` and shell auto-activation fail until it is trusted, so
the PM trusts it as part of workspace setup:

```sh
mise trust <worktree>     # plus `mise install` if the repo declares tools
```

This is conditional on a mise config actually being present — the PM does not
assume every repo uses mise, and skips trust entirely for repos without one.
`prompts/pm.md` step 1 (workspace) encodes this. Trust the main checkout once
the same way if it carries a mise config.

## Naming contract

| Item             | Rule                                                       |
| ---------------- | ---------------------------------------------------------- |
| tmux session     | `agents`                                                   |
| issue window     | `<repo-short>-<issue-number>` (e.g. `trander-flutter-233`) |
| PM pane          | `agents:<window>.0` (pane title `pm`)                      |
| worktree         | `${workspace_root}/.worktrees/<issue-number>`              |
| branch           | `feat/<issue-number>`                                      |
| review result    | `${workspace_root}/.worktrees/<issue-number>/tmp/review-result.json` |

These names are deterministic. Both Launcher and Watchdog reconstruct them
from `(repo, issue_number)` — no shared state file needed.

## Reviewer result contract

The PM/reviewer handoff uses an explicit JSON result file in the issue
worktree:

```text
tmp/review-result.json
```

The PM writes `running` before each review round and instructs the reviewer
to overwrite the file with the final result. Reviewer completion must be
decided from this file, not from tmux idle state, pane appearance, or output
polling.

Required JSON shape:

```json
{
  "status": "running",
  "must_fix": [],
  "optional": [],
  "verification": [],
  "summary": ""
}
```

Allowed `status` values:

- `running` — review has started and final data is not ready.
- `clean` — PM may push the branch and open the PR.
- `fix_required` — PM sends `must_fix` items back to the engineer.
- `blocked` — PM stops and reports the blocker.

If `tmp/review-result.json` is missing, malformed, still `running` 5 minutes
after reviewer assignment, or contains an unknown status, the PM treats the
reviewer as stalled and allows watchdog recovery. It must not open a PR from
reviewer pane output alone.

## v0.2 DB control plane

The v0.2 database contract is defined in `u_agents/db/README.md` and
`u_agents/db/001_agent_runs.sql`. It adds a PostgreSQL `agent_runs` table for
claimed work only. GitHub Issues with `status:ready` remain the queue source
of truth; DB rows are created only after the Launcher claims or leases work.

Launcher claim order is:

1. Observe a `status:ready` GitHub issue.
2. Acquire/upsert the DB claim and lease in `agent_runs`.
3. Re-verify the GitHub issue is still open and `status:ready`.
4. Swap the GitHub label to `status:in-progress`.
5. Start/resume the PM tmux pane and set `phase = 'pm_started'`.

The DB coordinates runners, but it is not the only truth. Before acting on a
row, a runner must verify external reality from GitHub, tmux, git, and
`tmp/review-result.json`.

Required runner environment for DB-backed operation:

| Name | Meaning |
| ---- | ------- |
| `U_AGENTS_DATABASE_URL` | PostgreSQL URL, for example `postgresql://u_agents:u_agents_dev_password@127.0.0.1:54329/u_agents`. |
| `U_AGENTS_RUNNER_ID` | Stable runner identity from config/env. |
| `U_AGENTS_MACHINE_ID` | Stable machine identity from config/env. |

Agents must not invent `U_AGENTS_RUNNER_ID` or `U_AGENTS_MACHINE_ID`.
Blank values and placeholders such as `runner`, `machine`, `placeholder`,
`changeme`, `todo`, or `example` are rejected. Launcher dry-runs require the
runner and machine identity because the dry-run output includes the DB claim
lease owner; live DB paths also require `U_AGENTS_DATABASE_URL` and `psycopg`.

### Making the env reproducible

These variables must be present in every process that touches the DB. There
are two delivery points, and both must agree:

1. **launchd jobs** (launcher + watchdog) read them from the plist
   `EnvironmentVariables` block. See "Scheduling under launchd" below.
2. **The tmux PM pane** runs the rendered `u_agents.mark_pr_open` command after
   opening a PR (see "PR-open bookkeeping"), so it needs the same values.
   Deliver them by sourcing a local env file from `.zshrc` (per the repo's
   AGENTS rule that env additions go in `.zshrc`, not `bootstrap.sh`):

   ```sh
   cp .u_agents_env.zsh.template ~/.u_agents_env.zsh
   chmod 600 ~/.u_agents_env.zsh
   $EDITOR ~/.u_agents_env.zsh   # fill in real RUNNER_ID / MACHINE_ID
   ```

   `.zshrc` sources `~/.u_agents_env.zsh` when present (guarded, so shells
   without it are unaffected). The real file lives outside the dotfiles repo
   and is never committed. Restart the tmux `agents` session after editing so
   the PM pane inherits the new values.

The `~/.u_agents_env.zsh` file and the plist identities ship with the
placeholders `runner` / `machine`, which identity validation rejects on
purpose — a forgotten edit fails loudly instead of claiming work under a bogus
identity.

### psycopg / Python environment

The live DB client imports `psycopg`. The Python interpreter that runs the
launcher, watchdog, PR watcher, and `mark_pr_open` must have it installed.
Install into that interpreter (or a venv it points at) and verify:

```sh
python3 -m pip install 'psycopg[binary]'
/opt/homebrew/bin/python3 -c 'import psycopg'   # the interpreter in the plist
```

If you use a virtualenv, point the plist `ProgramArguments[0]` at that venv's
interpreter. The PM prompt renders the launcher's `sys.executable` into its
`mark_pr_open` command, so it will reuse the same psycopg-enabled interpreter.

## Commands

From the `u_agents/` directory, `mise.toml` exposes short aliases. Python
tasks run from the dotfiles checkout root so `python3 -m u_agents.*` can
import the package. DB tasks run from `u_agents/` so Docker Compose reads
`compose.yml` and relative `db/` init scripts.

```sh
cd u_agents
mise run launcher-dry-run   # python3 -m u_agents.launcher --dry-run
mise run launcher           # python3 -m u_agents.launcher
mise run watchdog-dry-run   # python3 -m u_agents.watchdog --once --dry-run
mise run watchdog           # python3 -m u_agents.watchdog --once
mise run pr-watcher         # python3 -m u_agents.pr_watcher --once
mise run test               # python3 -m unittest discover tests
mise run db-up              # docker compose -f compose.yml up -d --wait postgres
mise run db-psql            # psql into local Postgres
mise run db-down            # docker compose -f compose.yml down
```

Service-management commands (`doctor`/`install`/`start`/`status`/`stop`)
are not implemented yet. Use the launchd setup below to schedule the
launcher and watchdog.

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
creation, prompt send, DB write) but still reads issue state from GitHub and
prints the `agent_runs` claim/lease and `pm_started` update it would perform.

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

The watchdog discovers active and stale work from `agent_runs`, then verifies
GitHub issue state and live tmux windows before pinging or commenting. If a DB
row points at a missing tmux window/pane, the watchdog records an observation
in `agent_runs` and skips pane action rather than trusting the row blindly.

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

`agent_runs` is the shared task/phase source. The local
`<dotfiles checkout>/u_agents/state/watchdog.json` file stores only pane-stall
details: last pane hash, unchanged-check count, pinged flag, and whether a
stall comment was already posted. It is anchored to the installed `u_agents`
package directory rather than the process current working directory. Override
with `--state-dir` when you want a different runtime location. The state write
uses atomic `tempfile + os.replace`, so a crash mid-write cannot corrupt the
file. `u_agents/state/` is local runtime data and ignored by git. If the state
file does become unreadable (manual edit, disk truncation), `load_state` warns
and resets to empty instead of deadlocking the watchdog loop.

Stalled-once-and-commented windows do not get re-commented until their pane
output changes.

### PR-open bookkeeping

The PR watcher only picks up `agent_runs` rows whose `phase` is `pr_open`,
`pr_watching`, or `ready_to_merge` **and** whose `pr_number` is set. After the
PM opens a PR it must persist that transition — relying on PM prompt memory is
not enough, and a missed update strands the run in `pm_started` forever. The PM
runs the helper CLI from its pane. Because the PM works inside the *target*
repo worktree (which does not contain the dotfiles `u_agents` package, and
whose mise/PATH may select a Python without `psycopg`), the command must put
the dotfiles checkout on `PYTHONPATH` **and** use the runner's own interpreter
rather than a bare `python3`:

```sh
PYTHONPATH=/Users/your-name/dotfiles \
  /opt/homebrew/bin/python3 -m u_agents.mark_pr_open --repo owner/name --issue 233 --pr 240
```

The PM prompt renders both automatically: `{u_agents_root}` (the dotfiles
checkout root) and `{u_agents_python}` (the launcher's `sys.executable`, i.e.
the interpreter that already imported `psycopg`). Both are shell-quoted, so the
PM never hardcodes them. This advances the row to `phase=pr_open` with
`pr_number` set (via the same `AgentRunsClient.update_pr_fields` the watcher
uses), so the next PR-watcher pass takes over. It needs the runner env and
`psycopg` like the other DB commands (see "Making the env reproducible").

The PM prompt (`prompts/pm.md`) includes this as a required, non-optional step
right after `gh pr create`.

### PR Watcher

The PR watcher reads `agent_runs` rows in `pr_open`, `pr_watching`, and
`ready_to_merge`, then verifies GitHub PR reality before any transition:
the PR must exist, its head branch must match `branch_name`, and merged/closed,
CI, and review-comment state are re-read from GitHub. Merged/closed/open state
is inferred from `gh`'s supported `state` (`OPEN`/`CLOSED`/`MERGED`) and
`mergedAt` fields — the watcher never requests a `merged` JSON field, which the
current `gh` CLI does not expose.

```sh
python3 -m u_agents.pr_watcher --once
mise run pr-watcher
```

It collects both top-level PR comments / review summaries (from `gh pr view`)
**and** inline review comments attached to specific diff lines (from
`gh api repos/{owner}/{repo}/pulls/{n}/comments`). The Gemini-style
high-priority inline note that motivated this is exactly such a comment. If the
inline-comment fetch fails or returns malformed output, the whole pass is
deferred (treated as a transient error like a failed `gh pr view`) rather than
proceeding as if the PR had no inline comments — so a fetch glitch can never
let a PR reach `ready_to_merge` without its comments being confirmed.

Transition rules (checked in order):

1. Merged PR -> `done`.
2. A fresh validated must-fix comment with `pr_review_fix_rounds = 0` ->
   `fixing`, increment `pr_review_fix_rounds`, mark that comment attempted, and
   assign one automated fix loop.
3. A validated must-fix comment already attempted once but still present ->
   `blocked` (it cannot be auto-fixed again and must not be ignored).
4. Comments needing user judgment:
   - With a live dispatcher configured (the production `main()` path) and at
     least one *fresh* (not-yet-handed-off) key: dispatch a validation prompt
     to the run's existing PM pane, mark those keys `handed_off`, and park the
     run in `phase = 'fixing'` (out of the watch set) until the PM re-arms it
     via `mark_pr_open`. The same key, if still ambiguous on re-entry, is
     already `handed_off` and falls through to a `blocked` escalation instead
     of being re-sent every tick.
   - With no live dispatcher (the conservative default / unit tests), or when
     every judgment key was already handed off, -> `blocked` (surface the
     decision to a human).
5. A fresh validated must-fix comment with `pr_review_fix_rounds >= 1` ->
   `blocked` (global round cap).
6. Green CI and no actionable/unresolved/judgment comments -> `ready_to_merge`.
7. Otherwise -> `pr_watching`.

#### Validation before fixing

Review comments are not always correct, so the watcher never blindly fixes
every bot/human comment. **Every** candidate comment — inline review comments,
top-level PR comments with a must-fix or forward-action signal,
`CHANGES_REQUESTED` review summaries, and a bare
`reviewDecision = CHANGES_REQUESTED` — is represented as a review comment and
flows through the same validation gate. None of them auto-trigger a fix on their
own. Each is classified as one of:

- `valid_must_fix` — confirmed correct and worth an automated fix.
- `valid_optional` — fine but not required; no fix.
- `invalid` — wrong/rejected/already-addressed; recorded, no fix.
- `needs_user_judgment` — cannot be confirmed automatically. In production the
  watcher first hands the fresh keys to the existing PM pane for validation (see
  the live handoff below) and only blocks a key once it has already been
  handed off and is still ambiguous; without a live dispatcher it blocks
  immediately so a human decides instead of auto-fixing.

The default runtime classifier (`default_validate_comment`) is deliberately
conservative and **never** returns `valid_must_fix` from marker text, a
`CHANGES_REQUESTED` summary, high-priority styling, or bot authorship alone —
those escalate to `needs_user_judgment`. A real `valid_must_fix` verdict comes
from an explicit validator (an agent) that the workflow injects. Invalid
comments record the rejection in metadata; replying on GitHub is a documented
follow-up, not a test requirement.

#### One automated attempt per comment

Each comment has a stable identity = GitHub comment id + a body hash. The
watcher persists per-comment state in `agent_runs.metadata.pr_review_comments`
keyed by that identity (`{verdict, attempted, ...}`), merging forward rather
than overwriting so a pass that sees an empty/partial comment list cannot drop
prior `attempted` keys. A `valid_must_fix` comment is auto-fixed at most once:
once `attempted` is set, the same id+hash on later passes is not fixed again —
but if it is still present it escalates to `blocked` instead of being ignored.
If the comment body changes, the hash (and key) changes, so it becomes a new
validation candidate eligible for one more attempt. This per-comment cap is in
addition to the global one-round cap (`pr_review_fix_rounds`).

#### Live handoff to the PM pane

The watcher owns no agent of its own. In production (`u_agents.pr_watcher`
`main()`), when the conservative default escalates a comment to
`needs_user_judgment`, the watcher hands the *fresh* keys to the run's existing
PM pane (`run.pm_pane` / `pm_pane_target(run.tmux_window)`) using the same tmux
delivery the launcher uses to seed the PM. The handoff prompt requires the PM
to validate each listed comment first, skip invalid/optional comments, address
only `valid_must_fix` ones, address each `id:body-hash` key at most once,
record verdicts, and then re-arm the watcher with the **exact** command

    PYTHONPATH=<dotfiles root> <python> -m u_agents.mark_pr_open --repo … --issue … --pr …

(built from the package root and `sys.executable`, never a bare interpreter
invocation, because the PM runs inside the target repo worktree where
`u_agents`/`psycopg` may be unavailable).

Duplicate handoffs are prevented by the per-comment `handed_off` flag in
`metadata.pr_review_comments`: only keys lacking it are dispatched, a successful
delivery parks the run in `phase = 'fixing'` (so it leaves the watch set while
the PM works), and a delivery failure leaves the key un-handed-off so it retries
next pass. Re-arming via `mark_pr_open` (phase -> `pr_open`) brings the run back
into the watch set; a still-ambiguous, already-`handed_off` key then escalates
to `blocked` instead of being re-sent.

The watcher records `pr_number`, `pr_review_fix_rounds`, `block_reason`, the
per-comment triage state, and small observations in `metadata`. It never
auto-merges; `ready_to_merge` means the user/operator can merge after their own
final check.

Suggested cron entry (single check per minute):

```cron
* * * * * /usr/bin/env python3 -m u_agents.watchdog --once >> ~/Library/Logs/u-agents-watchdog.log 2>&1
```

## Scheduling under launchd (macOS)

On macOS, prefer `launchd` over `cron`. Three example plists are tracked in
`examples/launchd/`:

| File | Job | Interval | Notes |
| ---- | --- | -------- | ----- |
| `local.u-agents.launcher.plist` | `u_agents.launcher` | 300 s (5 min) | One pass: resume sweep + claim one ready issue. |
| `local.u-agents.watchdog.plist` | `u_agents.watchdog --once` | 60 s (1 min) | One check pass; launchd owns the cadence. |
| `local.u-agents.pr-watcher.plist` | `u_agents.pr_watcher --once` | 300 s (5 min) | One PR-state pass; routes newly added PR comments to the PM pane. |

### Before installing

1. **Dry-run first**, on the command line, exactly as launchd will run it.
   Catch missing config, missing labels, or wrong python path while you can
   read the error directly:

   ```sh
   /opt/homebrew/bin/python3 -m u_agents.launcher \
     --config /Users/your-name/dotfiles/u_agents/config/repositories.yml --dry-run

   /opt/homebrew/bin/python3 -m u_agents.watchdog \
     --config /Users/your-name/dotfiles/u_agents/config/repositories.yml --once --dry-run

   /opt/homebrew/bin/python3 -m u_agents.pr_watcher --once
   ```

2. Edit the four placeholder paths in each plist:
   - `/opt/homebrew/bin/python3` — your python interpreter (must have `psycopg`)
   - `/Users/your-name/dotfiles/u_agents/config/repositories.yml` — your config
   - `/Users/your-name/dotfiles` — the dotfiles checkout (must contain `u_agents/`)
   - `/Users/your-name/Library/Logs/u-agents-*.log` — log destination

3. Edit the `U_AGENTS_*` values under `EnvironmentVariables` in each plist:
   - `U_AGENTS_DATABASE_URL` — the example ships the local `compose.yml` dev
     default; change it for any other database.
   - `U_AGENTS_RUNNER_ID` / `U_AGENTS_MACHINE_ID` — replace the `runner` /
     `machine` placeholders with real stable identities. Until you do, the job
     aborts with a "must not be a placeholder identity" error rather than
     claiming work under a bogus identity.

   Keep these in sync with `~/.u_agents_env.zsh` (the PM pane's copy) so every
   process agrees on identity. See "Making the env reproducible".

4. Confirm the plist interpreter has `psycopg`:

   ```sh
   /opt/homebrew/bin/python3 -c 'import psycopg'
   ```

5. Make sure `PATH` in the plist includes the directories holding `gh`,
   `tmux`, `git`, and `yq`. The examples set `/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin`.

### Install / start / stop / uninstall

```sh
# Install (copies to ~/Library/LaunchAgents and registers)
cp examples/launchd/local.u-agents.launcher.plist ~/Library/LaunchAgents/
cp examples/launchd/local.u-agents.watchdog.plist ~/Library/LaunchAgents/
cp examples/launchd/local.u-agents.pr-watcher.plist ~/Library/LaunchAgents/
launchctl load   ~/Library/LaunchAgents/local.u-agents.launcher.plist
launchctl load   ~/Library/LaunchAgents/local.u-agents.watchdog.plist
launchctl load   ~/Library/LaunchAgents/local.u-agents.pr-watcher.plist

# Trigger one run immediately (otherwise wait for the next interval tick)
launchctl start  local.u-agents.launcher
launchctl start  local.u-agents.watchdog
launchctl start  local.u-agents.pr-watcher

# Stop the most recent in-flight run (does NOT unload the schedule)
launchctl stop   local.u-agents.watchdog
launchctl stop   local.u-agents.pr-watcher

# Inspect schedule and exit codes
launchctl list | grep u-agents

# Tail the logs
tail -F ~/Library/Logs/u-agents-launcher.log \
        ~/Library/Logs/u-agents-watchdog.log \
        ~/Library/Logs/u-agents-pr-watcher.log

# Uninstall (unregister and remove)
launchctl unload ~/Library/LaunchAgents/local.u-agents.launcher.plist
launchctl unload ~/Library/LaunchAgents/local.u-agents.watchdog.plist
launchctl unload ~/Library/LaunchAgents/local.u-agents.pr-watcher.plist
rm ~/Library/LaunchAgents/local.u-agents.launcher.plist
rm ~/Library/LaunchAgents/local.u-agents.watchdog.plist
rm ~/Library/LaunchAgents/local.u-agents.pr-watcher.plist
```

### Why watchdog and PR watcher use `--once`

The watchdog also has a long-loop form (`--interval 60` without `--once`),
but under launchd you want `--once` so:

- Every tick is a fresh process; if the python process ever hangs or
  exhausts memory, launchd will simply launch a new one next interval.
- launchd surfaces exit codes per run (via `launchctl list`) which is more
  useful than a single long-lived process whose internal loop is opaque.
- Combining a python sleep loop with launchd duplicates the scheduler.

For the same reason, the launcher plist uses launchd's `StartInterval`
rather than a sleep loop in python. The PR watcher follows the same one-pass
pattern: each run observes current GitHub PR reality, hands any fresh review
comment keys to the owning PM pane, and exits. Per-comment `handed_off` /
`attempted` bookkeeping prevents the same stable comment from being routed or
fixed repeatedly.

### Suggested intervals

| Job | Interval | Rationale |
| --- | -------- | --------- |
| launcher | 300 s | New ready issues are rare; resume sweep is cheap but not free (one `gh issue list` per enabled repo). |
| watchdog | 60 s | Combined with default `--stall-checks=3`, a pane must be unchanged for ~3 minutes before a ping and another ~3 minutes after a ping before a stall comment. Decrease for tighter detection, increase to save API quota. |
| pr-watcher | 300 s | PR comments and CI can arrive after the PR is opened. A 5-minute cadence is enough to route each new stable comment for validation while keeping GitHub/DB polling modest. |

## Workflow

```
GitHub issue with status:ready
        │
        ▼
   Launcher picks one
        │
        ├─ acquires/upserts agent_runs claim + lease
        ├─ re-verifies issue open + status:ready
        ├─ swaps status:ready -> status:in-progress
        ├─ posts claim comment with tmux/worktree/branch coords
        ├─ ensures `agents:<window>` exists
        ├─ sends PM prompt into the window
        └─ writes phase=pm_started with tmux coords
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

        PR Watcher
                │
                ├─ verifies PR exists and head branch matches
                ├─ watches CI + review comments
                ├─ assigns at most one automated PR review fix loop
                └─ sets ready_to_merge / done / blocked

        Watchdog (separate loop)
                │
                ├─ reads active/stale agent_runs rows
                ├─ verifies GitHub issue + tmux reality
                ├─ capture-pane → hash → compare
                ├─ N unchanged checks → tmux send-keys ping
                └─ 2N unchanged after ping → one issue comment, then quiet
```

## Boundaries

- No long-running daemon.
- No semantic memory / vector DB.
- No queued/discovered ready issues in the DB before launcher claim.
- No PM/engineer/reviewer creation of the initial `agent_runs` row.
- No absolute worktree paths in `agent_runs`; store `worktree_basename` only.
- No automatic PR merge.
- No automatic worktree cleanup. Cleanup happens manually after PR merge.

## Verification

```sh
python3 -m unittest discover tests
python3 -m u_agents.launcher --help
python3 -m u_agents.watchdog --help
python3 -m u_agents.pr_watcher --help
python3 -m u_agents.mark_pr_open --help
```

Live `launcher`, `watchdog`, and `pr_watcher` runs require `gh auth login`, DB
environment variables, `psycopg`, and reachable local Postgres. A launcher
dry-run also requires `U_AGENTS_RUNNER_ID` and `U_AGENTS_MACHINE_ID` so it can
show the DB claim owner it would use.
