# Non-interactive review execution

Use only when the caller explicitly selects this backend and supplies a process
supervisor. This is a transport alternative, not a reduced review or permission
to deploy a service. Repository-specific queue, DB and PM contracts stay in the
repository's workflow, not this generic skill.

## Ownership

- The supervisor starts independent CLI invocations with argv arrays and stdin,
  never shell-interpolated prompts or terminal paste. It owns stdout/stderr drain,
  completion, the overall deadline, cancellation and process cleanup.
- Each request identifies the worktree, reviewed revision, selected lenses,
  contract and verification evidence. It retains exact execution identities.
- The coordinator selects the same mandatory floor and risk-dependent optional
  lenses as SKILL.md, records omissions with reasons, and supplies each lens its
  scoped instructions. Models/efforts remain those in SKILL.md.
- Run the selected lenses independently and concurrently, then perform a serial
  manager pass after every required lens has valid terminal output. A supervisor
  may invoke a separate manager CLI with the caller's model policy; it must not
  replace manager judgment with concatenation, voting, or rewritten findings.

## Result contract

- Return findings as the supervisor's structured final response. Do not also
  write a canonical reviewer-result file or wait for a second finalize prompt.
  The supervisor persists the returned content without changing its meaning.
- Lens prompts retain their perspective from SKILL.md; only output formatting
  changes. Manager input includes the contract, reviewed diff, all lens results,
  dropped-with-reason lenses and actual verification evidence.
- The manager reads surrounding source, classifies real/duplicate/out-of-scope
  findings, assesses the complete contract, and retains residual risks/test gaps.
  A missing or failed required lens cannot produce a successful review.
- CLI completion evidence and process exit are separate checks. Event arrival,
  elapsed time, a final-looking sentence or exit 0 alone proves neither a valid
  result nor semantic completion. Questions/blocked results stay blocked.
- Validate the provider's terminal protocol, exit status, output schema and
  current execution/revision before accepting the result. Never manufacture a
  clean result to repair a schema failure or permission denial.

## Failure and cleanup

- Drain stdout and stderr together even when output is large. Keep full logs
  local; publish only necessary redacted evidence.
- Apply one finite overall deadline across lenses and manager. Slow submitted
  inference is not an unsubmitted instruction. Do not replay it based on UI text.
- Stop only owned process groups; allow a bounded grace period, then verify
  cleanup. Uncertain ownership/survival requires inspection, not blind restart.
- A failure must identify which invocation failed. No implicit backend fallback,
  automatic retry allowance, or missing-lens clean result.
- Result delivery and result consumption by a caller are distinct. The caller's
  workflow owns acknowledgment/reconciliation and may not treat notification
  success as proof of semantic progress.

## Permissions and verification

Use the supervisor's explicit permission policy. Read-only analytical lenses
must report denied checks as unavailable. Execution lenses (visual/runtime)
need the existing isolated/vetted execution boundary; do not silently downgrade
their verification to source inspection. Read-only success is not evidence that
all runtime checks ran. Preserve golden tests and accepted deferrals unchanged.
