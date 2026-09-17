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

## Maintaining shared instructions

- `skills/` is shared by Codex and Claude; `codex/AGENTS.md` is linked from
  `~/.codex/AGENTS.md`. Keep changes model-neutral unless an execution workflow
  deliberately selects a model. Preserve caller-selected engines and permissions.
- Skill descriptions should state the capability and its decision boundary.
  Keep procedures in the body and conditional details in linked references.
  Do not make ordinary edits load a stack of preflight, clarification, and review skills.
- Base new rules on repeated history or a concrete failure mechanism. Prefer
  correcting the responsible skill to adding another global prohibition.
- When a skill path has moved, use the verified installed equivalent unless the
  caller pins its contents/version. Do not create a second copy to repair an alias.
- Preserve existing edits when revising skills. Validate changed frontmatter and
  reference links, and inspect representative task decisions; wording checks alone
  do not demonstrate improved agent behavior.
