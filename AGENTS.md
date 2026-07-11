- The symbolic link should be added to .zshrc instead of bootstrap.sh

## Skill / agent workflow instructions

- Keep generic skills generic. Do not add project-specific or workflow-specific
  branches such as "if using u_agents..." to broad skills. Put those rules in
  the dedicated workflow docs/skills instead.
- Prefer coarse, agent-ready implementation issues over many tiny sub-issues.
  The issue contract must be strong enough for an implementation agent to
  start: scope, out-of-scope, done-when, not-done-if, blockers, and required
  blackbox/runtime verification.
- Do not create sub-issues whose main purpose is policy clarification,
  specification reconciliation, or deciding what to do. Fix the parent issue
  contract first, then create implementable issues.
- Treat issue-internal phases as review/checkpoint gates, not automatically as
  separate GitHub sub-issues.

## Project-local workflow docs

- Keep repository-specific workflow/state rules close to their implementation.
- `u_agents` moved to https://github.com/uuta/uuter.
