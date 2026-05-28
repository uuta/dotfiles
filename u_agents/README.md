# u_agents/

v0.1 local agent runner. See [`docs/u-agents.md`](../docs/u-agents.md) for the
full design, configuration, and command reference.

Layout:

- `contract.py` — config + naming primitives.
- `launcher.py` — short-lived starter/resumer (`python3 -m u_agents.launcher`).
- `watchdog.py` — stall detector (`python3 -m u_agents.watchdog`).
- `prompts/pm.md` — PM prompt template sent into the tmux PM pane.

Tests live under `../tests/`. Run with:

```sh
python3 -m unittest discover tests
```
