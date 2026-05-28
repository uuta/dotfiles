---
name: learn
description: AI-Driven Learning Assistant. Structured learning based on Plan → Learn → Practice → Track methodology. Stores everything for a topic in a single ~/uuta/Learning/{topic}/curriculum.md page.
user_invocable: true
---
# AI-Driven Learning Assistant

## Overview

A structured learning skill based on the 4-step methodology: **Plan → Learn → Practice → Track**. Use AI as a *learning designer* — to create curricula, produce hands-on teaching materials, do peer-style review, and maintain progress visibility.

All learning content for a topic lives in **one single file** at `~/uuta/Learning/{topic}/curriculum.md`. The curriculum overview, every lesson, every self-check quiz, and every review result are sections within that one page — so the learner can scroll through everything in one place.

**Scope: foundational knowledge only.** This skill exists so the learner can quickly acquire a topic's *basics* — not a comprehensive reference. Keep curricula short (3–4 modules), keep each lesson tight (the minimum needed to grasp the core idea), and resist the urge to cover edge cases, advanced topics, or exhaustive APIs. If the learner wants depth later, they can run `/learn plan` again with a more specific sub-topic.

## Usage

```
/learn plan <topic>    # Create a new learning curriculum (one consolidated page)
/learn <topic>         # Start or continue learning a topic
/learn lesson          # Regenerate or fill in a missing lesson section
/learn review          # Peer-review your submitted practice work
/learn track           # Show TODO progress checklist
/learn まとめ           # Session summary
```

---

## Storage Layout

```
~/uuta/Learning/
  {topic}/
    curriculum.md      # Single page: overview + TODO + all lessons + all quizzes + all reviews
```

Use the Write/Edit tool or Bash to create and update this file in `~/uuta/Learning/{topic}/`.

---

## Single-Page Document Structure

`curriculum.md` is the **only** file. It is organized as:

```markdown
# {Topic} Learning Curriculum

## Overview
Brief description of what you will learn and why it matters.

## Curriculum (TODO)
- [ ] **Module 1: {Title}** — Objective: ... | Key Concepts: ... | Estimated Time: X hours
- [ ] **Module 2: {Title}** — ...
...

## References
- [Official Docs](url)
- [Key Resource](url)

---

# Lesson 1: {Module 1 Title}

**Status**: Not Started <!-- Not Started / In Progress / Complete -->

## Concepts

### {Concept 1}
Explanation...

```code
example
```

### {Concept 2}
...

## Common Mistakes
- Mistake 1: why it happens and how to avoid it
- Mistake 2: ...

## Self-Check Quiz
<!-- Complete these before running /learn review -->

### Q1 — Multiple Choice
**Question**: ...
A) ...  B) ...  C) ...  D) ...

**My Answer**: <!-- A / B / C / D -->

### Q2 — Fill in the Blank
**Question**: `____` is used when ...

**My Answer**: <!-- Write your answer here -->

### Q3 — Explain in Your Own Words
**Question**: In your own words, explain why ...

**My Answer**:
<!-- Write your answer here (2–3 sentences) -->

## Review
<!-- This section will be filled in by /learn review -->

---

# Lesson 2: {Module 2 Title}
... (same structure) ...

---

# Lesson N: ...
```

Each lesson is a top-level `# Lesson N: ...` heading separated by `---` rulers. This makes the file navigable in Obsidian's outline view.

---

## Behavior by Mode

### `/learn plan <topic>`

**Goal**: Create the consolidated curriculum page containing the overview, TODO checklist, and every lesson section in one file.

Steps:
0. **Fetch current information** for the topic before designing the curriculum:
   a. Use WebSearch to find: "{topic} latest features", "{topic} official documentation",
      "{topic} best practices {current year}", "{topic} release notes"
   b. Use WebFetch to retrieve key pages (official docs, release notes, changelog)
   c. Summarize key findings: new APIs, deprecated patterns, current idioms, version-specific features
   d. Use this research to inform all subsequent curriculum and lesson decisions
      — do NOT rely solely on training data for topic knowledge
1. Research the topic: identify official documentation, key concepts, and common learning pitfalls.
2. Divide the curriculum into **3–4 numbered modules** (hard cap: 4). Pick only the modules a beginner truly needs to grasp the fundamentals — skip advanced, optional, or "nice to know" material. Each module must include:
   - **Objective**: What the learner will be able to do after completing this module (one sentence)
   - **Key Concepts**: **2–3** core ideas (not more)
   - **Estimated Time**: Realistic time estimate (target ≤ 30 min per module)
3. Generate every lesson section in parallel using a Team, but **do not let any agent write to disk**:
   a. Call TeamCreate to create a team (e.g., team name: "lesson-gen-{topic}").
   b. For each module, spawn one Task agent (subagent_type: general-purpose) with a prompt that includes:
        - The topic name and lesson number (N)
        - The module's title, objective, key concepts, and estimated time
        - The lesson section format template (the `# Lesson N: ...` block above)
        - **Length budget**: keep the whole lesson under ~250 words (≈ 1 screen). Each Concept block ≤ 4 short sentences plus at most one tiny code example. Common Mistakes: max 2 bullets. Self-Check Quiz: exactly **3 questions** (one multiple choice, one fill-in-the-blank, one explain). No headings beyond the template.
        - Instruction: **return the lesson markdown as the message body — DO NOT write any files**. Do not cover advanced features, performance tuning, or edge cases — basics only.
      Launch all agents in a single message (parallel tool calls).
   c. Wait for all agents to complete and collect each returned lesson markdown.
   d. Call TeamDelete to clean up the team.
4. Assemble the single `curriculum.md`:
   - Top: title, Overview, Curriculum TODO checklist, References
   - Then: each lesson section in order, separated by `---` rulers
5. Write the assembled content **once** with the Write tool to `~/uuta/Learning/{topic}/curriculum.md`.
6. Print a summary: curriculum overview + the list of lesson titles now living inside `curriculum.md`.

**Important**: never create `lesson-01.md`, `lesson-02.md`, … as separate files. Everything goes into `curriculum.md`.

---

### `/learn <topic>` (Start or Continue)

**Goal**: Resume a learning session for a topic, or start one if no curriculum exists.

Steps:
1. Check if `~/uuta/Learning/{topic}/curriculum.md` exists.
   - If **not**, run the `plan` flow automatically first.
2. Read `curriculum.md` to identify the next incomplete module (`- [ ]`) in the Curriculum TODO list.
3. Scroll to the matching `# Lesson N: ...` section inside the same file and display it to the user.
4. Remind the user: "Fill in your **My Answer** fields in the `## Self-Check Quiz` of Lesson N, then run `/learn review` (or `/learn review N`)."

---

### `/learn lesson`

**Goal**: Regenerate or fill in a single lesson section inside `curriculum.md`. Normally `/learn plan` produces every section upfront — use this only when a section is missing or needs a refresh.

Steps:
1. Read `~/uuta/Learning/{topic}/curriculum.md` and find the first module that has no matching `# Lesson N: ...` section, or the module the user specifies.
2. Determine the lesson number `N` from its position in the Curriculum TODO list.
3. Generate the lesson markdown (Concepts, Common Mistakes, Self-Check Quiz with **exactly 3 questions** following the Quiz Generation Rules, empty Review section). Same length budget as `/learn plan`: under ~250 words total, basics only.
4. Use the Edit tool to insert or replace that specific `# Lesson N: ...` section inside `curriculum.md`. Preserve every other section. Keep the `---` rulers between lessons.
5. Display the regenerated section in the terminal.

---

### `/learn review`

**Goal**: Peer-review the user's submitted practice work for one lesson section, run a quiz gate, and mark that lesson complete only after demonstrated understanding.

Steps:
1. Determine which lesson is being reviewed:
   - If the user passed a number (`/learn review 3`), use that.
   - Otherwise pick the first lesson section whose `**Status**:` is `In Progress`, or the first `- [ ]` module in the Curriculum TODO if none is in progress.
2. Read the corresponding `# Lesson N: ...` section from `curriculum.md` — focus on **Concepts**, **Common Mistakes**, and **Self-Check Quiz**.
3. If all `**My Answer**` fields in that section are still blank placeholders (`<!-- ... -->`), prompt the user to fill them in and stop.
4. Review the submitted work like a knowledgeable peer:
   - **Correctness**: Are the answers correct? Point out errors with explanations.
   - **Best Practices**: Highlight idiomatic or better approaches.
   - **Improvements**: Suggest what could be done more cleanly or efficiently.
   - **Praise**: Acknowledge what was done well.
5. **Evaluate the Self-Check Quiz** holistically using the pre-generated questions in the section — do not regenerate them.
6. **Evaluate answers**:
   - **Pass** (≥ 60% understanding): use the Edit tool to fill in the lesson's `## Review` section with the review + quiz results, change its `**Status**:` to `Complete`, and mark `- [x]` for the matching module in the top-of-file Curriculum TODO list.
   - **Gaps found**: give targeted feedback. Ask: "Would you like to retry with new questions, or move on anyway?" If they retry, generate a new set of questions (one retry maximum), write the results into the `## Review` section either way.
7. Print a motivating summary of the review and quiz outcome.

**All edits stay inside `curriculum.md`** — do not create any sidecar files.

---

**Review section format** (written into the lesson's `## Review` block in `curriculum.md`):
```markdown
## Review

**Reviewed**: {date}

### Feedback
{Peer-style review of the submitted work}

### Corrections
{Specific corrections if any}

### What You Did Well
{Positive reinforcement}

### Next Steps
{What to focus on in the next lesson}

### Quiz Results
**Date**: YYYY-MM-DD
**Score**: X/Y
**Pass**: Yes / No (retried: Yes/No)

- Q1 (Multiple Choice) — Your answer: ... | Correct: ... | ✓ / ✗
- Q2 (Fill in the Blank) — Your answer: ... | Correct: ... | ✓ / ✗
- Q3 (Explain) — Your answer: ... | Evaluation: ... | ✓ / ✗

### Summary
{Brief note on strengths and any concepts to revisit}
```

---

### Quiz Generation Rules

- Draw questions directly from the lesson's **Concepts** and **Common Mistakes** content.
- Each quiz must include all 3 formats: multiple choice, fill in the blank, and explain in your own words.
- Multiple choice distractors should test common misconceptions, not random wrong answers.
- Fill-in-the-blank blanks should target critical syntax, keywords, or terminology.
- The "explain" question should require the learner to articulate the *why*, not just the *what*.

### Pass Threshold

- ≥ 60% of questions demonstrate understanding.
- The AI makes a holistic judgment — partial credit is fine, especially for the "explain" question.
- If gaps are found: offer one retry with new questions, or let the user opt to move on. Save quiz results regardless.

---

### `/learn track`

**Goal**: Show current learning progress.

Steps:
1. Ask the user which topic to track (or infer from context).
2. Read `~/uuta/Learning/{topic}/curriculum.md`.
3. Parse the **Curriculum (TODO)** checklist at the top of the file and display:
   - Completed modules (`- [x]`) with a checkmark
   - Current module (first `- [ ]`) highlighted
   - Remaining count
4. Print a motivational summary: "You've completed X of Y modules. Keep going!"

---

### `/learn まとめ`

**Goal**: Summarize everything covered in the current session.

Steps:
1. Review the lesson sections that were generated or reviewed in this session (look at `## Review` blocks whose `**Reviewed**:` date is today).
2. Produce a concise summary:
   - Topics covered
   - Key concepts learned
   - Insights from review feedback
3. Optionally offer to append the summary as a `## Session Summary — YYYY-MM-DD` block at the very bottom of `curriculum.md` (still one file, no sidecars).

---

## Important Notes

- Always confirm the topic before operating on files.
- When saving the file, use the Write tool with the full absolute path (e.g., `/Users/yutaaoki/uuta/Learning/Swift/curriculum.md`).
- If `~/uuta/Learning/` does not exist, create it with `mkdir -p ~/uuta/Learning/{topic}`.
- **One topic = one file.** Never split a topic across `lesson-01.md`, `lesson-02.md`, … — those existed in an older version of this skill and should not be created anymore. Use `## Lesson N: ...` sections inside `curriculum.md` instead.
- Prefer official documentation as the primary learning reference.
- When editing an existing `curriculum.md`, always use the Edit tool with enough surrounding context to target the exact lesson section — never rewrite the whole file unless `/learn plan` is being re-run from scratch.
