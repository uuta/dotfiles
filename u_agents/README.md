# u_agents/

v0.1 local agent runner. See [`docs/u-agents.md`](../docs/u-agents.md) for the
full design, configuration, and command reference.

Layout:

- `contract.py` — config + naming primitives.
- `control_plane.py` — v0.2 pure DB-control-plane constants and decisions.
- `launcher.py` — short-lived starter/resumer (`python3 -m u_agents.launcher`).
- `watchdog.py` — stall detector (`python3 -m u_agents.watchdog`).
- `prompts/pm.md` — PM prompt template sent into the tmux PM pane.
- `compose.yml` — local PostgreSQL 17 for v0.2 control-plane development.
- `db/` — `agent_runs` schema and contract docs.

Reviewer handoff is explicit: each issue worktree uses
`tmp/review-result.json` with status `running`, `clean`, `fix_required`, or
`blocked`. See [`docs/u-agents.md`](../docs/u-agents.md#reviewer-result-contract).

The v0.2 DB control-plane contract is documented in
[`db/README.md`](db/README.md). Current launcher behavior remains usable
without a database until DB runtime integration is added.

Tests live under `../tests/`. Run with:

```sh
python3 -m unittest discover tests
```
