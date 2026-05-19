---
name: notion-tmux-executor
description: Use when a user asks to read, create, append, replace, or update Notion content and the work should be delegated to a dedicated Claude Code tmux agent. Convert the natural-language request into a clear Notion operation contract, keep page body content as Markdown, create a unique run-scoped workspace under ${TMPDIR:-/tmp}, and send the task to the `notion-executor` agent instead of hand-writing raw Notion block JSON in the main agent.
---

# Notion Tmux Executor

## Goal

Route Notion read/write work through a dedicated tmux Claude executor so the main agent does not hand-write complex Notion JSON or perform risky page updates inline.

This skill is for the main/orchestrating agent. The tmux worker should use `agents/notion-executor.md`.

## When To Use

Use this skill for Notion work such as:

- reading a Notion page or database context
- creating a new page
- appending Markdown content to a page
- replacing page content
- creating a database item
- updating page/database properties
- capturing decisions, plans, meeting notes, research, or implementation status into Notion

Do not use this skill for generic Markdown drafting when no Notion read/write is requested.

## Operating Model

User-facing input stays natural language. Internally, convert it into a small operation contract and send that to the tmux Notion executor.

The main agent may draft Markdown content, but the executor owns:

- Notion target resolution
- Notion MCP/API calls
- database schema/property checks
- run-scoped temp directory creation
- before/after snapshots
- write verification
- final execution report

## Operation Contract

Send the executor a concise contract:

```yaml
operation: read | create | append | replace | update_properties | create_database_item
target: "<page URL, page ID, database/data-source URL, or search query>"
parent: "<parent page/data-source URL or ID, only for create/create_database_item>"
title: "<title for create/create_database_item, if applicable>"
content_markdown: |
  <Markdown body, if applicable>
properties:
  <plain property values, if applicable>
safety:
  confirm_before_write: true | false
  verify_after_write: true
  destructive: true | false
notes:
  - "<ambiguities, constraints, or user intent>"
```

Use `content_markdown` directly for short content. For long content, write it to a unique run directory and pass `content_file`.

## Run Directory Rule

Never use fixed temp paths such as `/tmp/notion-content.md`.

For every Notion write handoff, create a unique run directory:

```bash
run_dir="$(mktemp -d "${TMPDIR:-/tmp}/notion-agent.XXXXXX")"
```

Expected files:

- `manifest.yaml` or `manifest.json`
- `content.md`
- `before.md`
- `after.md`
- `result.md` or `result.json`

The executor may create the run directory itself. If the main agent creates files first, include the absolute `run_dir` and file paths in the handoff.

## Handoff Prompt

Use `tmux-sender` mechanics for multiline prompts.

Template:

```text
Use the notion-executor agent instructions.

Task: Execute this Notion operation safely.

Contract:
<operation contract>

Rules:
- Do not hand-write raw Notion block JSON unless the connected Notion tool has no Markdown/page-level alternative.
- Use a unique run directory under ${TMPDIR:-/tmp}/notion-agent.XXXXXX.
- For writes, fetch before state when possible.
- For append/create, write with Markdown content.
- For replace/destructive operations, stop for confirmation unless the contract explicitly says confirmation has already been given.
- For database item creation or property updates, fetch schema first and map plain property values to the correct Notion property types.
- Verify after write by fetching the page/item again.
- Report the Notion URL/ID, what changed, files written in the run directory, and any unresolved risks.
```

## Safety Policy

- `read` / `search`: no confirmation needed.
- `append`: no confirmation needed if target is unambiguous and low-risk; otherwise ask.
- `create`: no confirmation needed after parent is clear.
- `create_database_item`: fetch schema first; ask if required properties are missing or ambiguous.
- `update_properties`: fetch schema first; ask if property mapping is uncertain.
- `replace`: confirmation required unless the user explicitly approved replacement in the current turn.
- deletion/archive/move: out of scope for this skill unless explicitly requested and confirmed.

## Completion Criteria

The executor handoff is not done until it reports:

- target page/database resolved
- operation performed or blocked with reason
- before/after verification status for writes
- run directory path
- final Notion URL/ID
