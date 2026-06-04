---
name: wiki-knowledge-card
description: Generate a polished, self-contained dark-theme HTML "visual study sheet" for a term/word/concept in the Obsidian Wiki at ~/uuta/Wiki, then link it from a sibling Markdown note. Use when the user wants a visual vocabulary/knowledge card, an HTML version of a term explanation, or says things like "make a visual card for X", "knowledge card", "Wikiに<term>のhtmlを作って", or invokes /knowledge and asks for an .html. Produces <Term>.html (house style — hero, SVG diagrams, bilingual EN/JP) and ensures <Term>.md contains an open link.
user_invocable: true
---

# Wiki Visual Knowledge Card

Turn a term/word/concept into a beautiful, self-contained HTML "visual study sheet"
saved into the Obsidian Wiki, plus a Markdown note that links to it. Same content
spec as the `/knowledge` command (6-part), rendered in the house visual style.

## Inputs

- **Term** — the word/phrase/concept (required). May be English, 日本語, or a domain term.
- **Wiki dir** — defaults to `~/uuta/Wiki/`. Honor an explicit path if the user gives one.
- **Basename** — share ONE basename between the `.html` and `.md`. Match the casing already
  used in the Wiki: lowercase for single common words (`contingent`), Title Case for
  multi-word concepts (`Boundary Value Analysis`).

## Workflow

### 1. Produce the 6-part knowledge (same persona as `/knowledge`)
As an expert sharing specialized knowledge, gather, for the term:
1. A brief definition.
2. The category / field (and register, if a word).
3. Detailed explanation with **concrete, bilingual EN/JP examples**.
4. A diagram (etymology flow, comparison spectrum, or process) — rendered as inline SVG.
5. ~6 use cases.
6. ~10 related terms with short JP glosses.

Keep the bilingual (English + 日本語) treatment — it matches the existing Wiki cards.

### 2. Render into the house template
- Read `template.html` from this skill directory. **Keep its `<style>` block as-is** (that
  is the house style); you may only re-theme by adjusting `--accent` / `--accent-2` to suit
  the term's mood.
- Replace every `{{PLACEHOLDER}}` and adapt the section bodies. Add/remove/reorder sections
  to fit the content, but preserve: numbered `.sec-head`, `.card` containers, bilingual text,
  and **at least one original inline `<svg>`** illustration (hero) plus one diagram.
- Everything must be **self-contained**: no external CSS/JS, no web fonts, no remote images.
- Write to `<WikiDir>/<Basename>.html`.

### 3. Link it from the Markdown note
Ensure `<WikiDir>/<Basename>.md` contains the open-link line, following the existing
convention (see `Boundary Value Analysis.md`, `contingent.md`):

```
# <Title>

open "<absolute path>/<Basename>.html"
```

- If the `.md` is **empty or missing** → create it with just the H1 + blank line + `open "…"` line.
- If the `.md` **already has content** → insert the `open "…"` line right after the H1 (and a
  blank line), and **do not delete or overwrite** the existing body.
- If an `open "…"` line for this file already exists → leave it; just refresh the `.html`.

### 4. Report
Tell the user the files written and give the one-liner to view it:

```
open "<absolute path>/<Basename>.html"
```

## Rules
- Never overwrite a non-empty `.md` body — only insert the link line.
- Do not invent external assets; the `.html` must open correctly offline by double-click.
- Default location is `~/uuta/Wiki/` unless the user specifies otherwise.
- Reference cards to match for tone/structure: `~/uuta/Wiki/contingent.html`, `shady.html`.
