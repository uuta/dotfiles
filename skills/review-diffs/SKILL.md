---
name: review-diffs
description: Review git diffs with a manager-led workflow that preserves issue requirements. First derive a shared review contract from the user request and any linked issue or PR, then select review perspectives from a catalog (a mandatory floor plus diff-specific optional lenses, including a rendered UI/visual lens with web and Flutter-golden backends), run those perspectives as parallel tmux review agents, and finally perform a manager pass that checks total requirement coverage before summarizing.
allowed-tools: Bash(tmux:*), Bash(git:*), Bash(mkdir:*), Bash(gh:*), Bash(rg:*), Bash(sed:*), Bash(flutter:*), Bash(npx:*), Read
---

# Review diffs

## Goal

Use parallel reviewers to find problems in a diff without losing issue-level direction.

If the user wants this review to be part of a repeated `watch -> review -> fix -> repeat` supervisor loop around a coding agent in tmux, use `claude-tmux-review-loop`. This skill is the review dependency inside that larger loop.

The manager owns:

- review scope
- issue / PR requirement coverage
- which perspectives run for this diff
- accepted deferrals and out-of-scope boundaries
- final judgment

The tmux reviewers are specialists. They do not decide the total direction on their own.

### Vendor-neutral by design

Reviewers are launched as independent CLI agents inside tmux windows, not as engine-specific subagent tools. This keeps the skill usable with any coding-agent CLI. The examples below launch `claude`, but a window may instead run `codex` in full-autonomy mode (approval-policy never + full sandbox access) or another CLI. Do not rewrite this skill to use a single engine's native subagent/task tool — the tmux mechanism is what makes it reusable across engines.

For the same reason, reviewer instructions and the UI/visual backends must be self-contained: they rely on portable CLI tools (`flutter test`, a headless-browser screenshot CLI) and inline criteria, not on any one engine's MCP servers or skills. A `claude` reviewer MAY additionally lean on `ui-critique` / `visual-ui-contract` if available, but the prompt must still work without them.

## Workflow

1. Build a review contract before spawning reviewers
2. Create `docs/review/`, capture the diff, and classify the touched surfaces
3. Select perspectives from the catalog (floor + diff-specific optional)
4. Prepare the per-perspective output files
5. Launch parallel tmux reviewers for the selected perspectives
6. Give every reviewer the same contract plus one perspective lens
7. Poll until all reviewers finish
8. Perform a manager pass against the contract and the diff
9. Summarize findings to the user
10. Clean up review windows

## 1. Build the review contract

Before opening tmux reviewers, read enough context to define what "correct" means.

Preferred sources, in order:

- the user request
- linked GitHub issue / PR / review comments
- parent issue if the task is a sub-issue
- the current diff and touched files

If the user supplied an issue or PR number, read it. If the branch or commit message clearly references one, read that too. If there is no explicit issue, infer the contract from the request and changed files.

Create the review directory before writing any review artifacts:

```bash
mkdir -p docs/review
```

Write a short contract to `docs/review/contract.md` with:

- change goal
- canonical behavior after the change
- old behavior handling
- in-scope files / layers
- explicit out-of-scope boundaries
- accepted deferrals or known caveats
- review range being inspected
- visual contract / approved reference image / golden or screenshot baseline rules when the diff is screenshot-driven UI

Example skeleton:

```markdown
# Review Contract

- Goal: replace Auth0-based purchase identity with RevenueCat identity keyed by Supabase session.user.id.
- Canonical behavior: purchase login and entitlement checks must use the new auth core and expose CustomerInfo-derived state for routing.
- Old behavior handling: Auth0 `sub` and restore-as-startup-check must not remain in the main flow.
- In scope: purchase service, purchase state/notifier, purchase page, settings entry points, index bootstrap.
- Out of scope: onboarding orchestration, API upsert flow, unrelated UI cleanup.
- Accepted deferrals: stale generated lockfiles blocked by unrelated tooling issues may be noted but are not blockers.
- Review range: current worktree diff against origin/master.
```

This step is mandatory. Do not spawn reviewers before the contract exists.

The contract must live inside the current worktree so review state stays issue-scoped and inspectable later.

If the issue includes screenshot/mockup/ideal-image visual requirements, the contract must also state:

- the approved visual source
- the visual invariants being protected
- whether a visual shell / draft UI task should already exist
- which golden/screenshot/component visual tests are binding
- that baselines, thresholds, selectors, and visual expectations may not be changed without user approval
- what screenshot/golden evidence is required for review clean

## 2. Capture the diff and classify the touched surfaces

```bash
mkdir -p docs/review
git diff > docs/review/diff.txt
```

If the diff is empty, try a more explicit range such as:

```bash
git diff origin/main...
git diff HEAD~1
```

If the range is still ambiguous, stop and clarify the review target before continuing.

Then classify what the diff touches — this drives perspective selection in step 3:

```bash
git diff --name-only > docs/review/touched.txt
```

Note which of these surfaces appear:

- async / network / IO / subprocess / DB / background work
- new helpers, functions, files, or abstractions
- web UI files (`*.tsx *.jsx *.vue *.svelte *.css *.scss *.html`, component/page dirs)
- Flutter UI files (`*.dart`, `lib/**`, `pubspec.yaml`, widget/screen files)
- schema / migration files
- concurrency primitives (threads, isolates, locks, shared async state)
- user-facing strings or interactive UI (i18n / a11y)
- public API / route / DTO / proto changes
- auth, secrets, trust boundaries

## 3. Select perspectives from the catalog

Perspectives are decoupled from reviewer roles: one reviewer role runs one perspective lens passed as data. The catalog has a mandatory **floor** and diff-specific **optional** lenses.

### Floor — always run

- `requirements` — requirement compliance and scope control
- `correctness` — single-file bugs + cross-file integration
- `security` — auth/entitlement, secrets, injection, trust boundaries

The floor is non-negotiable: never let the diff classification talk you out of it. These are the lenses where a silent miss is expensive, so they run even for a one-line change.

### Optional — run when the diff warrants (cap ~3)

| Lens | Trigger |
|---|---|
| `resilience` | async / network / IO / subprocess / DB / background work touched |
| `reuse` | new helpers / functions / files / abstractions added |
| `ui-visual` | web UI or Flutter UI files touched (see backends below) |
| `data-migration` | schema / migration files touched |
| `concurrency` | threads / isolates / locks / shared async state touched |
| `i18n-a11y` | user-facing strings or interactive UI touched |
| `api-contract` | public API / route / DTO / proto changed |

Selection rule (the manager does this inline — no separate model needed for a small diff; for a large or ambiguous diff, a cheap focus agent may propose the set):

1. Always include the floor.
2. Add optional lenses whose trigger matches `docs/review/touched.txt`.
3. Cap optional lenses at ~3 to control cost; if more match, keep the highest-risk ones.
4. **Log which optional lenses matched but were dropped, and why.** No silent truncation — a dropped lens must be visible so the user can ask for it.

Record the chosen set (and the dropped-with-reason list) at the top of `docs/review/manager.md`.

## 4. Prepare the output files

Create one output file per selected perspective, e.g.:

- `docs/review/requirements.md` (floor)
- `docs/review/correctness.md` (floor)
- `docs/review/security.md` (floor)
- `docs/review/resilience.md` (optional, if selected)
- `docs/review/reuse.md` (optional, if selected)
- `docs/review/ui-visual.md` (optional, if selected)
- `docs/review/manager.md` (manager pass)

## 5. Launch parallel tmux reviewers

Create one dedicated tmux window per selected perspective. Each runs a coding-agent CLI (here `claude`) with permissions skipped for autonomy.

Model / effort policy:

- `review-req` uses `--model opus --effort high`. Requirement compliance needs the strongest judgment.
- Other specialist reviewers use `--model sonnet --effort high`. Each has a narrow lens, so sonnet-high is the cost-efficient default for parallel work.
- The manager pass (step 8) is run serially by the current session and inherits whatever model / effort the caller is using. Prefer running the skill itself under opus / high when possible.

### Engine policy

Reviewers are engine-agnostic (see "Vendor-neutral by design"). Pick the engine per lens:

- **Default is Claude.** An all-Claude run is the simplest and always correct — start here.
- **Vision-required lenses stay on Claude.** `ui-visual` reads golden-diff / screenshot PNGs, and the manager reads them too during UI confirmation. Never route these to an engine that cannot view local images.
- **Execution lenses need a stronger trust boundary.** `ui-visual` may run the reviewed branch's own code/dependencies (`flutter pub get`, `flutter test`, dev server, `npx playwright`). Run those steps only after the diff is already vetted, or inside an isolated/ephemeral worktree with no ambient credentials/network. Do not treat them like the read-only analytical lenses launched under blanket permission-skipped/full-autonomy settings.
- **`requirements` stays on the strongest model** (opus) — it is the judgment lens.
- **Pure-code lenses MAY run on codex** (`correctness`, `security`, `reuse`, `resilience`, and code-only optionals like `concurrency` / `api-contract`). Mixing engines here is a *quality* lever, not just cost: different models miss different bugs, so running e.g. `correctness` on both Claude and codex and merging in the manager pass widens coverage. Launch codex using the full-autonomy policy described in "Vendor-neutral by design" above, then inject the same lens prompt via tmux.
- **Tradeoff:** cross-engine runs add orchestration overhead (two CLIs, separate prompt injection). Default to all-Claude; opt into codex on high-stakes diffs where model diversity is worth it, or to offload cost.

Record the engine chosen per lens at the top of `docs/review/manager.md`, next to the selected perspectives.

Launch the floor windows always, plus one window per selected optional lens:

```bash
# floor
tmux new-window -n review-req -c "$(pwd)" 'claude --dangerously-skip-permissions --model opus --effort high'
tmux new-window -n review-correctness -c "$(pwd)" 'claude --dangerously-skip-permissions --model sonnet --effort high'
tmux new-window -n review-security -c "$(pwd)" 'claude --dangerously-skip-permissions --model sonnet --effort high'

# optional — only the ones selected in step 3; run ui-visual only after the trust-boundary caveat above is satisfied
tmux new-window -n review-resilience -c "$(pwd)" 'claude --dangerously-skip-permissions --model sonnet --effort high'
tmux new-window -n review-reuse      -c "$(pwd)" 'claude --dangerously-skip-permissions --model sonnet --effort high'
tmux new-window -n review-ui-visual  -c "$(pwd)" 'claude --dangerously-skip-permissions --model sonnet --effort high'
```

To run a lens on a different engine, swap that window's launch command (see **Engine policy** above) — the rest of the flow is unchanged. Cross-engine coverage (e.g. `correctness` on both Claude and codex) uses two windows for the one lens; the manager pass merges their findings.

Wait for each window to become ready by polling `tmux capture-pane` until the idle prompt appears.

## 6. Give every reviewer the same contract

Use `load-buffer` -> `paste-buffer` -> `C-m` for each window. Every prompt must include:

- `Read docs/review/contract.md first`
- `Read docs/review/diff.txt second`
- `Respect out-of-scope and accepted deferrals`
- `Do not judge overall success of the issue; only report findings from your lens`

### Floor 1: requirements

```text
Read docs/review/contract.md first, then docs/review/diff.txt.

Review only for requirement compliance and scope control.

Focus on:
- issue checklist items that are still unmet
- behavior that contradicts the canonical flow
- old behavior that should have been removed or redirected
- scope creep that solves the wrong problem
- known caveats that should be documented but are missing
- for screenshot-driven UI, missing visual evidence, weakened golden/screenshot tests, or drift from the approved visual contract

Do not spend time on generic style or speculative refactors.

Write to docs/review/requirements.md in the standard review format.
If there are no findings, say "No issues found."
```

### Floor 2: correctness (bug + integration)

```text
Read docs/review/contract.md first, then docs/review/diff.txt.

Review for correctness — both single-file bugs and cross-file integration regressions.

Single-file bugs:
- broken control flow, incorrect return values, wrong identifiers or stale state usage
- missing error handling that now breaks the intended flow
- null / type / lifecycle issues that are clearly reachable
- only report issues that are bugs now, not hypothetical ones

Cross-file integration:
- mismatches between service, notifier, and UI layers
- bootstrap / restore / routing state inconsistencies
- partial migrations that leave one side of an interface on the old model
- generated or config artifacts that now disagree with the code
- fragile assumptions across call boundaries

Write to docs/review/correctness.md in the standard review format.
If there are no findings, say "No issues found."
```

### Floor 3: security

```text
Read docs/review/contract.md first, then docs/review/diff.txt.

Review for security issues introduced or exposed by the diff.

Focus on:
- auth or entitlement bypass
- trust-boundary mistakes
- secret leakage
- unsafe token handling
- injection / path / network boundary issues

Write to docs/review/security.md in the standard review format.
If there are no findings, say "No issues found."
```

### Optional: resilience (failure paths + performance)

```text
Read docs/review/contract.md first, then docs/review/diff.txt.

Review for resilience — failure handling gaps and performance regressions.

Failure paths:
- async calls that can fail but are not caught or surfaced
- state that can be left inconsistent after failure
- missing cleanup, loading reset, or rollback on unhappy paths
- retries, timeouts, fallback behavior, or cancellation assumptions
- error propagation mismatches between lower layers and user-visible state

Performance:
- repeated expensive work on hot paths
- redundant network calls
- unnecessary allocations or recomputation
- blocking work introduced into startup or frequent UI flows

Treat network calls, plugin calls, subprocesses, file I/O, database access, API boundaries, and background tasks as the main risk areas.

Write to docs/review/resilience.md in the standard review format.
If there are no findings, say "No issues found."
```

### Optional: reuse / cohesion

```text
Read docs/review/contract.md first, then docs/review/diff.txt.

Review for comprehension debt, missed reuse, parallel implementations, responsibility drift, and unnecessary helper extraction.

Focus on:
- new helpers, functions, classes, hooks, components, validators, constants, enums, routes, errors, fixtures, or test builders that duplicate an existing responsibility
- local validation or authorization logic when a schema, guard, interceptor, decorator, domain validator, or shared helper already owns that behavior
- direct SQL, direct API calls, direct file access, or direct service calls that bypass established repository/client/service conventions
- new generic files such as `utils`, `helpers`, `common`, or `constants` when existing shared locations already exist
- new methods extracted only once with unclear responsibility or names that hide rather than remove complexity
- abstractions introduced before concrete variation exists
- code that appears to have inspected only the nearby file while ignoring adjacent patterns in the same layer

Prefer reuse, relocation, deletion, or consolidation over new abstraction.
Recommend abstraction only when there are at least two concrete implementations with the same responsibility and a stable shared concept.

Do not:
- suggest generic DRY cleanup that is unrelated to the diff's behavioral responsibility
- demand abstraction for one-off code
- report duplication unless it creates a concrete maintenance, correctness, or consistency risk
- fight the existing architecture just because a different general pattern exists

Write to docs/review/reuse.md in the standard review format.
If there are no findings, say "No issues found."
```

### Optional: ui-visual (rendered UI — web + Flutter golden)

This lens reviews the **rendered UI**, not just the diff text. Pick the backend by the touched files. It is self-contained: it relies only on portable CLI tools, so it works whichever engine runs the window.

This lens executes the reviewed branch's own code/dependencies. Run it only after the diff is already vetted, or inside an isolated/ephemeral worktree with no ambient credentials/network; do not put it under the same blanket `--dangerously-skip-permissions` / full-autonomy posture used for read-only analytical lenses.

```text
Read docs/review/contract.md first, then docs/review/diff.txt and docs/review/touched.txt.

Review the RENDERED UI, not just the diff text. Choose the backend by which files changed.

Trust boundary: this lens may execute the reviewed branch's own code/dependencies (dev server,
`npx playwright`, `flutter pub get`, `flutter test`). Run these steps only after the diff is
already vetted, or inside an isolated/ephemeral worktree with no ambient credentials/network.

If `ui-critique` / `visual-ui-contract` are available, prefer their canonical criteria; otherwise
use this abridged checklist.

=== WEB backend (*.tsx / *.jsx / *.vue / *.svelte / *.css / *.scss / *.html changed) ===
- Render the affected screen/component headlessly (e.g. `npx playwright screenshot <url> shot.png`,
  or the project's existing story/preview/dev server). Save the screenshot under docs/review/.
- If an approved screenshot / golden / mockup exists (a visual contract), judge FIDELITY:
  does the render match the reference? Do NOT weaken or change baselines, thresholds, or selectors.
- If no approved visual reference exists, judge QUALITY: visual hierarchy, spacing/rhythm, alignment, contrast/a11y,
  and "AI-generated" tells (generic gradients, over-centering, uniform card grids, decorative noise).
  Bias fixes toward subtraction and preserve the existing design world.

=== FLUTTER backend (*.dart / lib/** / pubspec.yaml changed) ===
- Work from the Flutter package dir. In a monorepo the app is often nested (e.g. `app/`,
  with tests under `app/test/`), not at the repo root — `cd` there first.
- Use the project's Flutter. If the project is fvm-pinned (a `.fvmrc` / `.fvm/` exists),
  invoke `fvm flutter ...`; otherwise `flutter ...`.
- Ensure deps are resolved before testing — a fresh worktree has no `.dart_tool/`:
    [ -f .dart_tool/package_config.json ] || flutter pub get
  If `flutter pub get` fails, report a VERIFICATION/TOOLING GAP, not PASS or REGRESSION.
- Find golden tests and map them to the touched widgets/screens:
    rg -l "matchesGoldenFile" test
  If there is no golden-test infra project-wide (`test/` missing or no matches), report one
  project-wide missing golden infrastructure observation.
- Run the relevant golden tests WITHOUT updating goldens (goldens are the source of truth):
    flutter test <relevant_test_paths>
  NEVER pass --update-goldens.
  If `flutter test` errors before producing golden-diff images (compile, resolution, missing
  tooling, or no `failures/` images), report a VERIFICATION/TOOLING GAP, not PASS or REGRESSION.
- PASS  -> visual fidelity is preserved for the covered widgets.
- FAIL with golden failure images -> Flutter writes failure images under a `failures/` dir next to the test. Read them:
    <name>_masterImage.png   (expected / golden)
    <name>_testImage.png     (actual)
    <name>_isolatedDiff.png  /  <name>_maskedDiff.png   (what moved)
  Describe where and how much drifted, and classify each as an INTENDED change (allowed by the
  contract) or a REGRESSION. Attach the image paths as evidence.
- If golden infra exists but a touched widget has NO golden -> report that widget as "missing
  golden coverage" (a requirement/coverage gap). Do not pass it silently.
- Golden / threshold / selector changes require user approval. Never make them yourself. A
  legitimate baseline update is a finding to ESCALATE, not something to apply.

Write to docs/review/ui-visual.md in the standard review format, with screenshot/failure-image
paths as evidence. If there are no findings, say "No issues found."
```

Other optional lenses (`data-migration`, `concurrency`, `i18n-a11y`, `api-contract`) follow the same shape: read the contract, review only through the named lens, write `docs/review/<lens>.md` in the standard format. Keep their prompts narrow and specific to the risk that triggered them.

## 7. Poll until all reviewers finish

For each window, poll every 5 seconds:

```bash
tmux capture-pane -p -t <window> -S -50
```

A reviewer is done when:

- the output file has been written, and
- the pane is back at the idle agent prompt

Use a bounded wait, not an infinite poll. If a window is not done after the local timeout (for example, 20 minutes), capture a larger pane tail and diagnose before continuing. If the pane shows a launch error, an unexpected interactive prompt, or an idle shell/agent prompt with no output file (including a codex window that failed to launch and looks idle), kill and relaunch that lens or escalate the verification gap to the user.

## 8. Manager pass is mandatory

After the tmux reviewers finish, do not immediately relay their output.

Perform one serial manager pass yourself:

1. Re-read `docs/review/contract.md`
2. Re-scan the diff
3. Read all reviewer outputs
4. **For each candidate finding, read the surrounding source beyond the diff to confirm it is real** — a finding that reads wrong in isolation but is fine given adjacent code is not a finding.
5. Decide which findings are real, duplicated, or out of scope
6. Check the issue-level checklist end to end

Judge findings against the contract, **not** by how many reviewers agreed. Reviewer agreement is a weak signal — a popular finding can still be wrong, and a lone reviewer can still be right. Contract + source confirmation is the arbiter.

Write the manager conclusion to `docs/review/manager.md` with:

- the selected perspectives (with the engine used per lens) and any dropped-with-reason optional lenses (from step 3)
- overall assessment
- remaining blockers
- accepted deferrals
- residual risks / test gaps

The manager pass must answer:

- Does the diff satisfy the intended issue direction?
- Is any required behavior still missing?
- Are any reviewers flagging problems that are outside the agreed scope?
- For screenshot-driven UI, did the implementation preserve the visual contract and avoid unauthorized baseline/threshold/selector changes? Are golden failures true regressions or intended changes, and is any touched widget missing golden coverage?

## 9. Summarize to the user

Findings come first.

When responding:

- lead with real findings ordered by severity
- include file and line references (and screenshot/golden-failure image paths for UI findings)
- call out requirement gaps before secondary observations
- explicitly state when no findings remain
- mention residual risks and verification gaps separately
- note which optional lenses were dropped, if any, so the user can request them

Do not simply aggregate reviewer counts. The output should reflect the manager's judgment.

## 10. Cleanup

Close the review windows when finished (only the ones you opened):

```bash
# floor
tmux kill-window -t review-req
tmux kill-window -t review-correctness
tmux kill-window -t review-security

# optional — include only if you opened it
tmux kill-window -t review-resilience
tmux kill-window -t review-reuse
tmux kill-window -t review-ui-visual
```

## Standard review format

```markdown
# {Category} Review

## Summary

{1-2 sentence overall assessment}

## Findings

### 1. {title}

- **Severity**: Critical / High / Medium / Low
- **Location**: `{file_path}:{line_number}`
- **Description**: {what is wrong and why}
- **Evidence**: {optional — screenshot / golden-failure image path for UI findings}
- **Suggestion**: {how to fix}
```

If there are no findings:

```markdown
# {Category} Review

No issues found.
```
