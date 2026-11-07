---
name: github-issue-image-upload
description: "Add or update images in a GitHub issue or PR body or comment from the CLI; fetching existing images is the github-issue-images skill's job."
allowed-tools: Bash(gh:*), Bash(git:*), Bash(bash:*), Bash(file:*)
---

# GitHub Issue Image Upload

## Goal

Put a local image into an issue or PR from the CLI.

`gh` has no upload command, so images are committed to one shared orphan branch, `issue-assets`, and embedded by commit-pinned URL. The bundled script does this without touching the working tree, the current branch, or the index.

## Use When

- an issue or PR body or comment needs a screenshot, mock, or diagram
- an image already in an issue needs replacing

Do not use when:

- reading images from an issue or PR (use `github-issue-images`)
- the image belongs in the product or docs (commit it normally on a feature branch)

Do not commit generated images into feature branches just to show them in an issue.

## Procedure

### 1. Upload

Run from the target repo, or pass `--repo-dir`. Issues and PRs share one number space, so `--issue` takes a PR number too.

```bash
<skill-dir>/scripts/upload-issue-images.sh --issue <N> /path/to/before.png /path/to/after.png
```

Each file goes to `issue-<N>/<basename>` on the branch. Stdout has one line per file, and everything else goes to stderr:

```text
![before.png](https://github.com/<owner>/<repo>/blob/<commit>/issue-<N>/before.png?raw=true)
```

Prefer PNG. GitHub does not reliably render SVG from blob URLs, and the script warns about it.

### 2. Insert the line

Start from the current body so that it is preserved:

```bash
gh issue view <N> --json body --jq .body > /tmp/issue-<N>-body.md
# add the printed lines where they belong
gh issue edit <N> --body-file /tmp/issue-<N>-body.md
```

For a comment:

```bash
gh issue comment <N> --body-file /tmp/issue-<N>-comment.md
```

Use `gh pr view`, `gh pr edit`, and `gh pr comment` the same way for a PR.

### 3. Check it

```bash
gh issue view <N> --json body --jq .body | grep -F 'issue-<N>/'
```

The line must be there. In a private repo, images render only for logged-in users with repo access. That is why the `blob/...?raw=true` form is used rather than `raw.githubusercontent.com`.

## Replacing an image

Upload the new file under the same name, then put the new line in the issue. URLs are pinned to a commit, so old issue text keeps showing the old image until it is edited.

## Pitfalls

- Never delete the `issue-assets` branch or old `issue-*-diagram` branches. Their images would stop rendering.
- Never merge `issue-assets` into anything. It is an orphan branch, so a PR cannot be opened from it.
- Older issues with `issue-*-diagram` URLs are legacy and fine as is. Do not migrate them.
