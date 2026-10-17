@/Users/yutaaoki/.codex/RTK.md

## Working preferences

- Complete the requested work through its required verification and final artifact. A progress update or first implementation is not a handoff; continue unless a real blocker or an explicit stop remains.
- Use prior answers and authorization. Resolve routine, reversible local choices from context; ask only about a missing decision that materially changes the result or an additional action outside the authorized scope.
- Keep fixes tied to the requested behavior. Triage review findings before implementing them; generic cleanup and speculative hardening do not extend a fix loop. Preserve accepted deferrals and required runtime/visual evidence.
- Reuse verification that still covers the current change. After a fix, rerun affected checks and any explicitly required suite; do not repeat broad checks just for reassurance.

## Local skills

- Shared skills live at `~/dotfiles/skills`, exposed through `~/.agents/skills` and `~/.claude/skills`. Load only skills and references that help the current task.
- If a referenced skill path is stale, locate the installed skill with the same name and verify that its workflow fits before continuing. Report the path correction briefly; do not stop solely because an alias moved. Preserve an explicitly pinned version/content requirement.
- Keep project-specific workflow rules in that project. Follow the current issue's worktree and role assignment; being assigned implementation does not mean starting another implementation agent.
