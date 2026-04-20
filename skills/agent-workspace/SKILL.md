---
name: agent-workspace
description: Prepare and clean up a project workspace and git worktrees so agents can work safely per issue. Use `main/` as the base checkout and `.worktrees/<issue_number>/` as the dedicated worktree directory. Do not create worktrees directly under home or inside an existing checkout. Use branch names like `feat/<issue_number>`. Use this for requests such as "create a worktree", "set up an agent workspace", or "prepare an issue-specific working directory".
allowed-tools: Bash(git:*), Bash(ls:*), Bash(find:*), Bash(mkdir:*), Bash(rm:*)
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

### 5. Clean up an unused worktree

```bash
git -C <project>/.worktrees/<issue_number> status --short
git -C <project>/main worktree remove <project>/.worktrees/<issue_number>
```

If the branch is no longer needed, delete it separately afterward.

## Notes

- Using the issue number as the basename makes it easy to align branch names, tmux panes, and issue IDs
- This skill is limited to workspace and worktree management
- Leave issue selection and tmux assignment to other skills
