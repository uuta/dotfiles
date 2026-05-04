---
name: worktree-env
description: Copy or link ignored env-like files into a git worktree from a source checkout or secrets directory using a tracked manifest such as `docs/env-paths.txt`. Use for worktree bootstrap when a repo declares local runtime/build config paths, especially after `agent-workspace` creates or reuses an issue worktree.
allowed-tools: Bash(git:*), Bash(rg:*), Bash(ls:*), Bash(find:*), Bash(mkdir:*), Bash(ln:*), Bash(cp:*), Bash(rm:*), Bash(readlink:*)
---

# Worktree Env

## Purpose

Bootstrap ignored local config files into a worktree from a manifest.

This skill is generic. It is not Flutter-specific.

Use it when:
- a worktree needs ignored env or local config files to run, build, or test
- the repo tracks a manifest of required local file paths
- you want a reproducible way to link or copy those files into a worktree

Do not use it when:
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
.env.dev
.env.stg
.env.prod

# Runtime env files
assets/.env.dev
assets/.env.stg
assets/.env.prod
```

## Default behavior

- For agent-created worktrees, prefer `--mode copy --force` so agents get a
  self-contained snapshot of local config and do not mutate the source checkout
- Keep the source of truth outside the worktree
- Do not infer the required file list from search results alone
- Never create empty placeholder env files when a manifest source is missing

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
scripts/link-manifest.sh --source <source_root> --target <target_root> --mode copy --force
```

Useful variants:

```bash
scripts/link-manifest.sh --source <source_root> --target <target_root> --mode check
scripts/link-manifest.sh --source <source_root> --target <target_root>
scripts/link-manifest.sh --source <source_root> --target <target_root> --force
scripts/link-manifest.sh --source <source_root> --target <target_root> --manifest <custom_manifest>
```

### 5. Verify

Required checks after agent-worktree bootstrap:

```bash
scripts/link-manifest.sh --target <target_root> --mode check
git -C <target_root> status --short --ignored
```

For Flutter apps using `flutter_dotenv`, also verify that asset env files are
not zero-byte placeholders:

```bash
wc -c <target_root>/assets/.env.dev <target_root>/assets/.env.stg <target_root>/assets/.env.prod
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

- `agent-workspace` should call this skill automatically when a target worktree
  contains `docs/env-paths.txt`
- `claude-tmux-pm` should not assign runtime/native work to Claude until the
  manifest check passes
