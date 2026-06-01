---
name: blackbox-test-design
description: Turn an input specification into a minimal, high-coverage black-box test set using Equivalence Partitioning + 2-value Boundary Value Analysis. Use when designing or reviewing test cases for functions, forms, validators, or APIs from their input domains (ranges, formats, enums) — not from source code. Triggered by phrases like "design test cases", "what should I test for this input", "boundary tests", or "EP/BVA for this field".
user_invocable: true
---

# Black-Box Test Design (EP + BVA)

## Goal

Given an **input specification** (one or more parameters with their domains/constraints),
produce the *smallest* set of test cases that still covers the behavior — using
Equivalence Partitioning (EP) for the interior and 2-value Boundary Value Analysis (BVA)
for the edges. Black-box only: design from the spec, never from the implementation.

## Core principle (the rule this skill encodes)

- **Ordered/contiguous domain** (numbers, dates, lengths, counts, money) → **EP + BVA**.
- **Unordered/categorical domain** (enums, booleans, code sets, free text) → **EP only**
  (no neighbors exist, so BVA does not apply).
- The interior of a valid partition is homogeneous → cover it with **one** representative.
- The risk lives at the **edges**. Off-by-one errors shift a boundary by exactly one,
  so for each boundary test the **boundary value + its just-outside neighbor** (2-value BVA).
- **Do NOT** add interior near-boundary values (e.g. for 1–100, skip 2 and 99) — they sit in
  the valid class and catch nothing the boundary itself doesn't. That is robust 3-value BVA;
  it has diminishing returns and is not the default.
- **Internal thresholds are boundaries too.** If behavior changes mid-range (tax brackets,
  shipping tiers, a discount at qty ≥ 10), each threshold gets its own BVA treatment — it is
  not "interior."

## Procedure

1. **List inputs.** For each parameter, state its domain and constraints from the spec.
2. **Classify each domain** as ordered or unordered (see core principle).
3. **Partition (EP).** For each input, derive:
   - the **valid** partition(s) — inputs the system should accept;
   - the **invalid** partition(s) — below range, above range, wrong type/format, empty/null,
     and any other rejected class.
   Pick **one representative per partition** (use a nominal interior value for a valid range).
4. **Add boundaries (BVA), ordered partitions only.** For each boundary, add the boundary
   value and the value just across it (2-value). Mark which should be accepted vs rejected.
   Apply to every internal threshold as well.
5. **Combine & dedupe.** Test set = EP representatives ∪ BVA edge values.
6. **Multiple inputs.** Default to **one-variable-at-a-time**: vary one input across its
   partitions while holding the others at a valid nominal value. Use a **decision table**
   only when conditions genuinely interact to produce different outcomes.
7. **(Optional) Error guessing.** Add experience-based probes the spec doesn't name:
   empty string, whitespace-only, zero, negative, leading zeros, very long input,
   special/Unicode characters, duplicate submission. Clearly label these as supplementary.

## Output format

A markdown table, plus a one-line note on what was deliberately *not* tested (and why).

| # | Input(s) | Covers (partition / boundary) | Valid? | Expected result |
|---|----------|-------------------------------|--------|-----------------|

Keep the set minimal. If you drop something a naive reader might expect (e.g. interior
near-boundary values), say so explicitly so the omission reads as a decision, not a gap.

## Worked example — `age` accepted when 18–60

- Domain: integer, ordered. Valid partition 18–60; invalid partitions <18 and >60;
  plus non-integer / empty as invalid.
- EP representatives: `40` (valid), `10` (too low), `70` (too high), `"abc"` (non-integer).
- BVA (2-value) at each boundary: `17, 18` (lower), `60, 61` (upper).
- Combined set: `{ "abc", 10, 17, 18, 40, 60, 61, 70 }`.

| # | age | Covers | Valid? | Expected |
|---|-----|--------|--------|----------|
| 1 | 40 | valid interior (EP) | ✅ | accepted |
| 2 | 17 | lower boundary − 1 (BVA) | ❌ | rejected |
| 3 | 18 | lower boundary (BVA) | ✅ | accepted |
| 4 | 60 | upper boundary (BVA) | ✅ | accepted |
| 5 | 61 | upper boundary + 1 (BVA) | ❌ | rejected |
| 6 | 10 | below-range class (EP) | ❌ | rejected |
| 7 | 70 | above-range class (EP) | ❌ | rejected |
| 8 | "abc" | wrong-type class (EP) | ❌ | rejected |

*Not tested: 19 and 59 (interior near-boundary values) — redundant under EP, covered by #1.*

## Anti-patterns to avoid

- Enumerating many values inside one partition (no added coverage).
- Adding boundary ± 1 *inside* the valid class (3-value padding like 2/99 for 1–100).
- Applying BVA to unordered/categorical inputs.
- Designing from the code instead of the spec (that's white-box, not black-box).
