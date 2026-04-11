---
name: worktree-env
description: Link or copy ignored env-like files into a git worktree from a source checkout or secrets directory using a tracked manifest such as `docs/env-paths.txt`. Use when a worktree needs local runtime config to run, build, or test, but do not use by default for every worktree.
allowed-tools: Bash(git:*), Bash(rg:*), Bash(ls:*), Bash(find:*), Bash(mkdir:*), Bash(ln:*), Bash(cp:*), Bash(rm:*), Bash(readlink:*)
---

# Worktree Env

## Purpose

Bootstrap ignored local config files into a worktree without mixing that concern into workspace creation or tmux assignment.

This skill is generic. It is not Flutter-specific.

Use it when:
- a worktree needs ignored env or local config files to run, build, or test
- the repo tracks a manifest of required local file paths
- you want a reproducible way to link or copy those files into a worktree

Do not use it when:
- the task is edit-only and does not need local secrets or runtime config
- the repo has no tracked manifest yet
- the user explicitly wants a different local-config mechanism

## Default manifest

Prefer a tracked manifest at:

```text
docs/env-paths.txt
```

The manifest belongs in the repo, not in the skill.

Format:
- one repo-relative path per line
- blank lines allowed
- `#` comments allowed

Example:

```text
# Android / native build
.env

# Runtime env files
assets/.env.dev
assets/.env.stg
assets/.env.prod
```

## Default behavior

- Prefer symlinks
- Use copy only when the user asks for copy semantics or symlinks are unsuitable
- Keep the source of truth outside the worktree
- Do not infer the required file list from search results alone

## Procedure

### 1. Identify the target worktree

Usually this is the current repo checkout or a path like:

```text
<workspace>/.worktrees/<issue_number>
```

### 2. Identify the source root

The source root must mirror the manifest's relative paths.

Common choices:
- the main checkout, when it already has the ignored local files
- a user secrets directory such as `~/.config/<project>/env`

### 3. Read the manifest

Default:

```text
<target>/docs/env-paths.txt
```

If the manifest does not exist, stop and ask whether to create it. Do not silently guess.

### 4. Link or copy the files

Use the bundled script:

```bash
scripts/link-manifest.sh --source <source_root> --target <target_root>
```

Useful variants:

```bash
scripts/link-manifest.sh --source <source_root> --target <target_root> --mode check
scripts/link-manifest.sh --source <source_root> --target <target_root> --mode copy
scripts/link-manifest.sh --source <source_root> --target <target_root> --force
scripts/link-manifest.sh --source <source_root> --target <target_root> --manifest <custom_manifest>
```

### 5. Verify

Recommended checks:

```bash
scripts/link-manifest.sh --target <target_root> --mode check
git -C <target_root> status --short --ignored
```

### 6. Audit when needed

Use `rg` only as an audit tool to find manifest drift, not as the primary source of truth.

Search patterns depend on the stack. Common examples:
- `.env`
- `dotenv`
- `process.env`
- `String.fromEnvironment`
- `os.environ`
- build scripts that open env files directly

If audit shows a new required local file path, update `docs/env-paths.txt`.

## Notes

- This skill should stay separate from `agent-workspace` and `claude-tmux-pm`
- Those skills manage workspace and assignment; this one manages local config bootstrap
- It is valid to skip this skill when a worktree does not need local env files
