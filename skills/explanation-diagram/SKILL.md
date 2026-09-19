---
name: explanation-diagram
description: Create simple visual diagrams that explain a situation, phenomenon, system structure, or process to a person through pictograms and arrows. Use when a picture would clarify relationships, causes, or what works and what is missing; not for numerical charts or detailed engineering specifications.
---

# Explanation Diagram

Make the explanation understandable from the picture before the reader studies its labels. Use one visual message per image, large recognizable pictograms, clear connections, and very little text. Match the user's language.

## Visual benchmark

Inspect [the user-approved example](references/approved-example.png) with an image-viewing tool before the first diagram in a task. It establishes the preferred density: a few large objects, arrows, a conspicuous broken connection, short labels, and one takeaway. It is a historical project example, not evidence about the current project or a template whose services and failure states should be copied.

The rejected approach was a row of text-heavy cards, each containing status, explanation, issue numbers, and evidence, followed by more explanatory panels. Replacing prose with boxes is not enough. Remove words and let position, symbols, and connections carry the explanation.

## Decide what the picture says

- Extract one concrete question or takeaway from the conversation. Do not turn a focused explanation into a complete architecture inventory.
- Choose a visual relationship: a route for a process, a causal chain for a phenomenon, grouped objects for structure, or a before/after pair for a change. A few main objects, often three to six, are usually enough.
- Use available facts. For a diagnosis, distinguish confirmed causes from hypotheses. For progress, distinguish code written, simulated behavior, real integration verified, missing work, and unknown state only where relevant.
- Assess connections as well as components. Two implemented components do not prove that their connection works. Do not turn missing evidence into a confirmed failure, or label a component fully working because a mock-based test passed.
- Label historical or proposed states briefly so they cannot be mistaken for current reality. Keep dates, source links, detailed evidence, and qualifications outside the picture unless essential to interpreting it.

## Draw visually

- Prefer recognizable objects: phone, person, server, cloud, storage, document, speaker, or simple physical analogies. Use spatial grouping for ownership and boundaries.
- Make arrows directional and easy to follow. Show a missing connection with a broken cable, gap, or cross; use a dashed connection with a short label for a proposed or unverified path.
- Use a restrained palette. For status diagrams, teal/green can indicate confirmed portions, amber partial or simulated verification, coral a confirmed gap or failure, and grey unknown or contextual portions. Pair color with labels or symbols; do not rely on color alone.
- Give labels names or short phrases, not explanations. Prefer "未接続" or "テスト音声" to sentences. Avoid dense legends, nested boxes, issue IDs under every object, and technical identifiers the audience does not need.
- Use generous whitespace and a large focal point. If it still looks like a document, simplify the content before shrinking the type. Put secondary explanations in accompanying prose or a separate diagram.
- Include at most one short takeaway sentence when it adds value. Do not add a large title that overstates what the evidence proves.

## Choose the output method

- Prefer **image generation** for pictorial explanations and easy-to-read visual metaphors. Give the image tool the exact short labels, layout, factual states, and exclusions. Use the benchmark as a style reference when supported, without transferring its project facts.
- Prefer **SVG** when exact labels, precise connections, or an editable artifact matter. Draw pictograms and connections rather than reproducing a text-card layout. A combination of generated illustrations and SVG labels is useful only when it improves clarity enough to justify the extra work.
- For this workflow, deliver an image rather than Mermaid source by default. Honor an explicit request for another format.
- Follow the available image tool's rules for editing existing images. When tools are unavailable, use an available SVG workflow and report any rendering limitation without claiming the output was visually verified.
- For SVG, render it in an appropriate browser/rendering environment and capture a PNG screenshot; retain the editable SVG. Use an available screenshot skill when it fits the environment. Do not require a particular browser, provider, or model. For generated raster images, the image itself is the visual deliverable; no redundant screenshot is needed.

## Inspect and deliver

View the actual output at approximately the size the user will see. Check:

- Can the intended relationship or problem be recognized within a few seconds, without reading a paragraph?
- Are the objects and arrow directions unambiguous? Are real paths and simulated/test paths distinguished when relevant?
- Are short labels readable, correctly spelled, and unclipped, including Japanese text?
- Do colors, checkmarks, and crosses accurately reflect the evidence rather than merely decorate the picture?

Correct material rendering or meaning errors before delivery. If the user says it is hard to understand, first remove secondary concepts and text; do not merely change styling or add a legend.

Show the image with minimal accompanying prose. Provide an editable source link when available and source/evidence links outside the image when needed. Do not repeat the full explanation after the diagram or display an already-visible generated image twice.
