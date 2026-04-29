---
name: github-issue-images
description: Fetch and inspect screenshots embedded in GitHub issues or pull requests, especially `github.com/user-attachments/assets/...` URLs that often return `404` without GitHub authentication. Use when an issue or PR includes images and an agent needs the actual pixels from CLI or tmux.
allowed-tools: Bash(gh:*), Bash(curl:*), Bash(rg:*), Bash(sed:*), Bash(find:*), Bash(mkdir:*), Bash(file:*)
---

# GitHub Issue Images

## Goal

Read GitHub-hosted screenshots reliably from CLI.

The main failure mode this skill covers is:

- issue or PR text is readable with `gh`
- embedded screenshot URLs use `github.com/user-attachments/assets/...`
- plain `curl` returns `404`
- the image is actually downloadable when the request uses `gh auth token`

Do not declare the screenshot unavailable until the authenticated path has failed.

## Use When

- a GitHub issue or PR includes screenshots or mock images
- direct fetch of a `user-attachments` URL fails
- a tmux agent needs the image locally for visual review

Do not use when:

- the image is already attached in the current chat thread
- the asset is a normal public URL that downloads without GitHub auth
- the task does not need the actual image content

## Procedure

### 1. Read the issue or PR text

Examples:

```bash
gh issue view 120 --repo uuta/trander-flutter
gh pr view 119 --repo uuta/trander-flutter --comments
```

### 2. Extract attachment URLs

Search for GitHub issue attachment URLs from the raw body, not the rendered terminal view:

```bash
gh issue view 120 --repo uuta/trander-flutter --json body --jq '.body' | \
  rg -o 'https://github\.com/user-attachments/assets/[A-Za-z0-9-]+'
```

For PR comments:

```bash
gh pr view 119 --repo uuta/trander-flutter --json body,comments \
  --jq '.body, (.comments[].body // empty)' | \
  rg -o 'https://github\.com/user-attachments/assets/[A-Za-z0-9-]+'
```

### 3. Download with GitHub auth

Use the bundled script:

```bash
scripts/download-github-attachment.sh \
  --url 'https://github.com/user-attachments/assets/<id>' \
  --output /tmp/issue-120-ideal.png
```

This script uses:

```bash
gh auth token
```

and sends:

```bash
Authorization: Bearer <token>
```

to the attachment URL before following redirects.

### 4. Verify the file

Recommended checks:

```bash
file /tmp/issue-120-ideal.png
ls -lh /tmp/issue-120-ideal.png
```

If you need to inspect the pixels in-session, use `view_image` on the saved file path.

### 5. Only then report a blocker

If download still fails:

- check `gh auth status`
- confirm the URL is a `github.com/user-attachments/assets/...` link
- retry once with the script
- only then say the screenshot is unavailable

## Naming Convention

When an issue includes multiple images, prefer explicit filenames:

- `/tmp/issue-120-actual.png`
- `/tmp/issue-120-ideal.png`
- `/tmp/pr-119-review-1.png`

This makes later review prompts less ambiguous.

## Notes

- `404` from unauthenticated `curl` is not conclusive for GitHub issue attachments.
- Prefer `--json body` or `--json body,comments` when extracting URLs. The rendered `gh issue view` output may wrap text and make extraction brittle.
- Prefer this skill before asking the user to re-upload a screenshot.
- Keep the image-fetch step separate from implementation. This skill is about access and inspection, not UI coding.
