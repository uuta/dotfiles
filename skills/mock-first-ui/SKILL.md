---
name: mock-first-ui
description: Build app screens from approved HTML mock sets without per-screen visual drift by freezing shared tokens, components, a gallery, a UI constitution, a reference screen, and serial verification gates. Use when HTML mocks are binding design specs and screen implementation is dispatched in batches to coding agents, especially after independent screen work has caused inconsistent styling.
---

# Mock-First UI

## Purpose

Build app screens from approved HTML design mocks without per-screen design drift.

Use it when:
- an HTML mock set is the binding design spec and screens will be implemented from it
- implementation is dispatched batch-by-batch to a coding agent (codex, claude, or another CLI)
- previous per-screen dispatch produced inconsistent styling that needed re-integration

Do not use it when:
- there is no approved mock (freeze the mock first; verbal specs drift)
- the change is a single-screen tweak inside an already-established vocabulary

## Core principle: two layers

Drift happens because each screen batch can invent its own style values. Extraction
alone does not stop that. You need extraction PLUS a repo-visible law that forbids
invention.

- **Skill layer (this file)** — manager orchestration: batch order, dispatch
  discipline, verification gates. Only the manager reads this.
- **Repo layer (`docs/design/ui-constitution.md` + tokens + gallery)** — binding for
  every implementer agent. Coding agents do not read manager skills; anything that
  must constrain them lives in the repo.

## Procedure

### 0. Preconditions

- Approved mock set, e.g. `design/<version>/`, with shared CSS custom properties in
  `design/<version>/shared/*.css`. If styles are duplicated per page, consolidate
  into shared CSS custom properties first (mock-side refactor, re-approve renders).
- A no-cache static server for mock verification (plain `http.server` serves 304s;
  strip `If-Modified-Since`/`If-None-Match`, send `Cache-Control: no-store`).
- Screenshot tooling (playwright CLI) that renders BOTH the mobile width and the
  desktop width the mock supports. Media-query frame modes can crush flex children
  invisibly at one width while looking fine at the other.

### 1. Batch 0 — design vocabulary (no screens)

One batch, dispatched before any screen work:

1. **Tokens**: extract every CSS custom property (colors, spacing, radius, shadows,
   type scale) into the app's token module (e.g. `AppTokens` + `TextTheme` in
   Flutter). Write a 1:1 mapping table to `docs/design/tokens-map.md`
   (CSS var -> token name -> value). If the variable count grows large or multiple
   platforms consume the tokens, switch to generating the token file from the mock
   CSS with a script instead of maintaining the table by hand.
2. **Shared components**: every part that appears on 2+ mock screens (nav, top bars,
   card container, pills/badges, segment tabs, inputs, primary CTA, list rows,
   icon buttons).
3. **Gallery screen**: a dev-only route rendering all components in one place.
   Pixel-compare it against the mock parts. This is where the vocabulary freezes.
4. **Golden/screenshot tests** per component, so later drift fails CI instead of
   relying on reviewer eyes.
5. **Constitution**: write `docs/design/ui-constitution.md` (template below) and
   commit it. This is the law implementer agents are pointed at.

Review-gate Batch 0 like any other batch before proceeding.

### 2. Constitution template (repo file, adapt values)

```markdown
# UI Constitution

1. The mock under design/<version>/ is the binding spec. When in doubt, read the
   mock's shared CSS variables, not a screenshot.
2. No raw style values in screen files: no literal colors, text styles, paddings,
   radii, or shadows. Everything goes through the token module.
3. A new component must be added to the shared component library AND the gallery
   screen before it is used in a screen. No screen-local component definitions.
4. Follow the reference screen (<path>) for composition patterns.
5. UI changes go mock-first: update the mock, re-render, get approval, then code.
```

### 3. Reference screen

Implement ONE screen first (pick the most representative) and polish it to pixel
match against the mock. Every later batch prompt says "follow the reference screen's
patterns". A concrete exemplar beats abstract rules.

### 4. Screen batches — serial, never parallel

- Dispatch screen batches one at a time. Serial dispatch lets each batch read the
  previous batch's code as established convention; parallel dispatch is the root
  cause of drift.
- Every screen-batch prompt starts with the same header:
  - binding mock file(s)
  - path to the constitution, tokens, gallery, and reference screen
  - the rule: compose existing components only; new components go to the shared
    library + gallery first

### 5. Verification per batch

- Mechanical drift check — screen files must not contain raw style literals, e.g.
  (Flutter): `rg "Color\(0x|TextStyle\(|EdgeInsets\.|BorderRadius\." lib/features`
  should return nothing outside the token/component modules.
- Render the implemented screen and the mock side by side at the same width;
  compare. Screenshot mocks at BOTH supported widths.
- Full-page screenshots paint `position: fixed` elements at their first-viewport
  position (they can appear mid-page); verify fixed bars with a viewport-height
  shot before filing a layout bug.
- Run the diff through the standard review gate (`review-diffs`) with the reuse and
  ui-visual lenses selected; goldens are the source of truth and are never updated
  without owner approval.

### 6. Change management

Any UI-affecting change after the freeze goes mock-first: mock edit -> rendered
screenshots (both widths) -> owner approval -> implementation batch. Never patch the
app's UI ahead of the mock.

**Mock edits are reviewed as diffs, not as fresh renders.** When a batch touches an
already-approved mock page: (a) the dispatch prompt must say "merge into the existing
page — do not replace existing sections" and name what must survive; (b) before
presenting renders, diff the mock against its previous committed version and list every
REMOVED element for explicit owner sign-off. A new render can look fine while silently
deleting previously-approved content (this exact failure deleted an approved
monthly/annual plan section once — the render review passed because it only judged what
was visible, not what had vanished).

## Notes

- Vendor-neutral: the implementer can be codex, claude, or any CLI agent — the
  constitution and prompts carry the constraints, not agent-specific tooling.
- The manager owns commits, review gates, and pixel verification; the implementer
  owns code. Do not let the implementer update goldens or the constitution
  unilaterally.
