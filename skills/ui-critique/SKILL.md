---
name: ui-critique
description: Critique a rendered UI for visual hierarchy, clutter, "AI-generated" tells, and drift from an established design world — when there is no golden image to match against, only a sense that "it looks off / too busy / too AI". Renders the real pixels (headless browser screenshot), judges against a named failure-mode taxonomy, and returns ranked, subtraction-biased fixes that preserve the world. Triggered by "review this UI", "this screen looks cluttered/AI-ish", "critique this design", "why does this feel off", "keep the vibe but clean it up".
user_invocable: true
---

# UI Critique (render-first design critique)

## Goal

Given a built UI (HTML/component/screen) and, ideally, a reference that defines its
**world** (palette, type, emblem — e.g. a sibling "golden" screen), produce a *ranked,
actionable* critique of why it reads as cluttered / generic / "AI-made", and the
*minimal* changes that fix it **without leaving the world**. Bias every fix toward
**subtraction** — the cure for clutter is removal, not addition.

## When to use / not use

- **Use** when there is no approved image to match, only a judgment call: "looks busy",
  "feels AI", "keep the vibe but make it premium", "is this good design?".
- **Do NOT use** when an approved screenshot/mockup exists and the job is fidelity to it
  → that is `visual-ui-contract`.
- **Do NOT use** to *generate* a new interface from scratch → that is `frontend-design` /
  `neo-frontend-design`. This skill judges what already renders.

## Core principle (the rule this skill encodes)

- **Critique pixels, not code.** Always render the UI and screenshot it. A diff or a CSS
  read cannot tell you a screen is cluttered. If you did not look at the rendered image,
  you did not review the UI.
- **The world is the palette + type + emblem + density, anchored to a reference.** "Keep
  the world" almost never means "don't change colors" — the palette is usually fine. It
  means **don't change how many elements are loud at once**. Most "off" UIs fail on
  *density and hierarchy*, not on hue.
- **One screen, one job, one focal point.** Find the single thing the screen exists to do.
  Everything that does not serve it is a candidate for removal or demotion.
- **Subtraction first.** Prefer "delete X / quiet Y / merge Z" over "add a new element".
  A finding that adds visual weight to fix a too-heavy screen is almost always wrong.
- **Severity scales with screen lifetime and role.** A 2-second loader, a glanceable
  result, and a studied settings page have different bars. Establish the role first.

## Named failure-mode taxonomy (the detector for "AI-ish")

Score the screen against these. Each is a *named tell* with a *why* and a *default fix*.
"AI-generated feel" is not a vibe — it is usually two or three of these stacked.

| # | Failure mode | Tell on screen | Why it reads bad | Default fix |
|---|--------------|----------------|------------------|-------------|
| 1 | **Redundant encoding** | One state shown by many indicators (e.g. spinner + bar + step-tracker + % + dots all = "loading") | Reads as a parts checklist, not a decision; mixing indeterminate + determinate is logically contradictory | Pick **one** primary indicator; delete the rest |
| 2 | **Everything glows** | Glow/shadow/gradient on nearly every element | Uniform emphasis = no emphasis; no focal point, no rest | Let **one** element own the glow; flatten the others |
| 3 | **Gradient-clipped body text** | Rainbow/`background-clip:text` on running copy or a single highlighted word | The single most common generative signature | Solid color for text; reserve gradient for the hero emblem |
| 4 | **Saturation density** | Many fully-saturated accents firing at once | Eye has nowhere neutral to land; cheap-loud, not premium | Cut accent count; keep one "now/active" accent, mute the rest |
| 5 | **Decoration noise stack** | grain + blobs + streaks + particles together | Competing background motion/texture buries the content | Keep at most one ambient layer; dial it down |
| 6 | **Templated stack** | Evenly-spaced, symmetric vertical list of components, no rhythm | "Assembled from parts" look; no intentional asymmetry or negative space | Introduce hierarchy: vary scale/spacing, add real whitespace |
| 7 | **Motion budget blown** | 4+ independent animations looping at once | Restless; nothing to anchor the eye | Cap concurrent loops (≈1–2); align timing/easing |
| 8 | **Badge/pill inflation** | pill + tag + chip + badge on most elements | Decorative chrome inflates importance of trivial parts | Keep badges for genuine status only |
| 9 | **Focal contention** | Two+ elements equally loud in the optical center | Eye ping-pongs; no clear "look here first" | Promote one to hero, demote the rest to support |
| 10 | **World drift** | Palette/type/emblem diverge from the reference screen | Breaks product cohesion | Re-anchor to the reference's tokens; change density, not identity |

## Procedure

1. **Establish role & world.** State the screen's job and lifetime (loader / result /
   form / hub). Identify the reference that defines the world (a sibling screen or token
   set). If none is given, infer the world from the screen's own dominant palette/type and
   say so.
2. **Render the real pixels.** Open the UI in a headless browser at a real device viewport
   and screenshot it. See *Rendering recipe* for the gotchas.
3. **Capture the states that matter.** For animated/transient screens, capture more than
   one moment (e.g. loader: early / mid / end). Do not critique a single frozen frame of a
   moving screen.
4. **Find the one job and the one focal point.** Name them explicitly.
5. **Run the taxonomy.** Walk the table; record each tell that fires with where it appears.
   "AI-ish" = call out which 2–3 modes are stacked.
6. **Separate keep vs cut.** List the *world anchors to preserve* and the *elements to
   remove/quiet*. Be explicit that the palette stays if the problem is density.
7. **Rank fixes by impact, biased to subtraction.** Highest-leverage removal first.
8. **Sanity-check against the world.** Confirm no fix changes the product's identity
   (hue/emblem/type), only its density/hierarchy.

## Rendering recipe (practical gotchas)

- **`file://` is often blocked** by the browser tool. Serve the directory:
  `python3 -m http.server <port>` in the file's folder, then load `http://localhost:<port>/…`.
- **Auto-advancing / infinite-animation screens won't hold still.** Make a temp copy with
  the redirect/timer neutralized (e.g. `sed 's/location.href = NEXT;//'`) and screenshot the
  copy. Never edit the original to freeze it.
- **Use a real device viewport** (e.g. 390×844 for the phone shell), not the default window.
- **Respect `prefers-reduced-motion`** if you need a calm frame, but also judge the
  full-motion state — restlessness is a finding, not something to hide.
- **Look at the siblings.** Screenshot the reference/world screens too, so "drift" and
  "keep the world" are evidence-based, not asserted.

## Output format

1. **Verdict line** — role + the 2–3 stacked failure modes, in one sentence.
2. **Redundancy/inventory table** when one job is over-encoded (list every element doing
   the same job; the point lands harder as a table than as prose).
3. **Keep (world anchors)** — bullet list of what must not change.
4. **Cut / quiet** — ranked bullet list. Each: *what* → *why it reads cluttered/AI* →
   *the minimal change* → *(confidence)*.
5. **Resulting hierarchy** — one line describing the intended N-tier focus after cuts
   (e.g. "phrase → one analyzing emblem → one quiet progress = 3 tiers").

Keep findings few and high-leverage. If you decline to flag something a naive reviewer
would (e.g. "add a subtitle"), say why — so the omission reads as a decision, not a miss.

## Worked example (shape only)

> **Verdict:** 2-second loader; reads AI-ish from *redundant encoding* + *everything glows*
> + *gradient-clipped text* stacked.
>
> **Inventory (one job "loading", six indicators):** conic halo · ping rings ×3 ·
> waveform · 3-step tracker · progress bar+% · title dots.
>
> **Keep:** gradient mic emblem, condensed-italic phrase, lime status dot, warm near-black.
>
> **Cut/quiet:** ① collapse six progress indicators to one determinate halo — delete bar,
> %, steps, ping rings *(high)*. ② un-clip the rainbow on body text → solid white *(high)*.
> ③ one ambient layer only (blobs *or* streaks), grain down *(med)*. ④ demote waveform to a
> thin baseline so the disc is the sole focal point *(med)*.
>
> **Resulting hierarchy:** phrase → one analyzing emblem → one quiet progress (3 tiers).

## Anti-patterns to avoid

- Reviewing from the CSS/diff without rendering. The image is the input.
- Vibes-only verdicts ("feels cluttered"). Name the failure mode and where it fires.
- "Fix" the palette when the problem is **density** — changes identity, doesn't reduce noise.
- Adding elements (a divider, a label, another card) to a screen that is already too busy.
- A 30-item checklist. A few stacked named tells explain "AI-ish" better than a long list.
- Critiquing one frozen frame of an animated screen as if it were the whole experience.
