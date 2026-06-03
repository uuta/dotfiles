# u_agents/

v0.2 DB-backed local agent runner. See [`docs/u-agents.md`](../docs/u-agents.md) for the
full design, configuration, and command reference.

Layout:

- `contract.py` — config + naming primitives.
- `control_plane.py` — v0.2 pure DB-control-plane constants and decisions.
- `agent_runs.py` — PostgreSQL `agent_runs` runtime access layer.
- `launcher.py` — short-lived starter/resumer (`python3 -m u_agents.launcher`).
- `watchdog.py` — stall detector (`python3 -m u_agents.watchdog`).
- `pr_watcher.py` — DB-backed PR phase watcher (`python3 -m u_agents.pr_watcher`).
- `prompts/pm.md` — PM prompt template sent into the tmux PM pane.
- `compose.yml` — local PostgreSQL 17 for v0.2 control-plane development.
- `db/` — `agent_runs` schema and contract docs.

Reviewer handoff is explicit: each issue worktree uses
`tmp/review-result.json` with status `running`, `clean`, `fix_required`, or
`blocked`. See [`docs/u-agents.md`](../docs/u-agents.md#reviewer-result-contract).

The v0.2 DB control-plane contract is documented in
[`db/README.md`](db/README.md). Live runtime paths require
`U_AGENTS_DATABASE_URL`, `U_AGENTS_RUNNER_ID`, `U_AGENTS_MACHINE_ID`, local
Postgres, and `psycopg`; unit tests and `--help` paths do not import psycopg.

Tests live under `../tests/`. Run with:

```sh
python3 -m unittest discover tests
```
