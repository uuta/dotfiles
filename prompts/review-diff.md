---
description: Legacy alias for review-diffs
---

This legacy singular command delegates to the plural manager-led
`review-diffs` workflow. Do not perform the old source-only review and do not
create `docs/review.md`.

Invoke the installed `review-diffs` skill by name.

Run that workflow in the current worktree against the requested diff. Preserve
its required artifacts under `docs/review/`, including the manager pass and any
UI screenshot paths or explicit verification/tooling gaps.
