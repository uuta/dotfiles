---
name: agent-workspace
description: Prepare and clean up a project workspace and git worktrees so agents can work safely per issue. Use `main/` as the base checkout and `.worktrees/<issue_number>/` as the dedicated worktree directory. After creating or reusing a worktree, copy ignored env/local config files declared by `docs/env-paths.txt` from `main/` into the worktree. Do not create worktrees directly under home or inside an existing checkout. Use branch names like `feat/<issue_number>`. Use this for requests such as "create a worktree", "set up an agent workspace", or "prepare an issue-specific working directory".
allowed-tools: Bash(git:*), Bash(ls:*), Bash(find:*), Bash(mkdir:*), Bash(rm:*), Bash(cp:*), Bash(test:*)
---

# Agent Workspace Skill

## Purpose

Keep agent working directories separate from the main repository checkout.

Recommended layout:

```text
<project>/
  main/
  .worktrees/
    <issue_number>/
```

- `main/` is the base checkout
- `.worktrees/<issue_number>/` is the dedicated worktree for one issue
- `.agents/` is optional and can be added later if needed

## Guardrails

- Do not create issue-number directories directly under home
- Do not create worktrees inside `main/`
- Do not let agents work in a user's existing active checkout
- Use one worktree per issue
- Use branch names like `feat/<issue_number>`
- Use `<issue_number>` as the worktree basename by default
- Do not remove a dirty worktree even if the related PR was already merged

## Procedure

### 1. Decide the workspace root

If the current repository is at `.../main`, treat its parent directory as the workspace root.

Example:

- repo: `/path/to/trander-rust/main`
- workspace root: `/path/to/trander-rust`

### 2. Check existing worktrees

```bash
git -C <project>/main worktree list
```

Reuse the existing worktree if the target issue already has one.

### 3. Create the issue worktree

```bash
mkdir -p <project>/.worktrees
git -C <project>/main worktree add <project>/.worktrees/<issue_number> -b feat/<issue_number>
```

If you want to make `origin/main` explicit:

```bash
git -C <project>/main fetch origin
git -C <project>/main worktree add <project>/.worktrees/<issue_number> -b feat/<issue_number> origin/main
```

### 4. Use it as the working directory

Give the agent `.worktrees/<issue_number>/`, not `main/`.

### 5. Copy ignored env/local config files

Immediately after creating or reusing a worktree, check whether the target repo
has a tracked manifest:

```text
<project>/.worktrees/<issue_number>/docs/env-paths.txt
```

If it exists, copy every listed path from `<project>/main` into the worktree.
Do this before assigning an agent or running build/test commands.

Use the `worktree-env` skill's script when available:

```bash
/Users/yutaaoki/dotfiles/skills/worktree-env/scripts/link-manifest.sh \
  --source <project>/main \
  --target <project>/.worktrees/<issue_number> \
  --mode copy \
  --force
```

Then verify:

```bash
/Users/yutaaoki/dotfiles/skills/worktree-env/scripts/link-manifest.sh \
  --target <project>/.worktrees/<issue_number> \
  --mode check
git -C <project>/.worktrees/<issue_number> status --short --ignored
```

If the manifest exists but any source file is missing in `main/`, stop and
surface it as a setup blocker. Do not create empty placeholder env files for
agent worktrees.

If the manifest does not exist, do not guess secret paths from `rg` output as
the primary source of truth. You may audit env usage and propose adding
`docs/env-paths.txt`, but do not silently assume the worktree is runnable.

### 6. Clean up an unused worktree

```bash
git -C <project>/.worktrees/<issue_number> status --short
git -C <project>/main worktree remove <project>/.worktrees/<issue_number>
```

If the branch is no longer needed, delete it separately afterward.

## Notes

- Using the issue number as the basename makes it easy to align branch names, tmux panes, and issue IDs
- This skill is limited to workspace and worktree management
- Leave issue selection and tmux assignment to other skills
