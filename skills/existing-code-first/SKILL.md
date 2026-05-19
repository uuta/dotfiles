---
name: existing-code-first
description: Use for any coding implementation, bug fix, refactor, test addition, code review, or agent handoff where new code may be added or existing behavior may be changed. Before creating new functions, classes, files, utilities, services, hooks, components, schemas, constants, validators, test helpers, or dependencies, search existing code for equivalent or similar responsibilities and prefer reuse, extension, relocation, or consolidation over parallel reimplementation.
---

# Existing Code First

## Goal

Prevent parallel implementations and comprehension debt by checking existing code before adding new code.

Use this skill as an implementation and review guardrail. It applies even when the requested change is small.

## Before Writing Code

1. Identify the responsibility being added: domain rule, formatting, validation, authorization, API call, persistence, state management, UI component, test setup, or utility behavior.
2. Search for existing code with the same or adjacent responsibility using `rg`.
3. Inspect nearby modules in the same layer and one or two existing call sites.
4. Prefer the least surprising path:
   - call the existing implementation
   - extend it if its responsibility already covers the new case
   - move it to a shared location if it is useful but poorly placed
   - consolidate duplicates before adding another variant
5. Create a new implementation only when reuse would distort responsibility, preserve an obsolete contract, or introduce higher risk. In that case, leave a short rationale in the final response or code review notes.

## Search Checklist

Search by several names, not only the name you planned to create.

- Domain words: entity names, route names, event names, status names, error names.
- Responsibility words: `format`, `parse`, `validate`, `authorize`, `permission`, `guard`, `mapper`, `adapter`, `client`, `repository`, `factory`.
- Type and constant names: DTO names, enum values, field names, config keys.
- Existing conventions: suffixes and layer names already used in the repo.

Prefer `rg` and `rg --files`. If the codebase has generated files or vendor directories, exclude them unless they are the source of truth.

## Review Checklist

Flag a finding when a diff adds a new implementation while an existing one appears to cover the same responsibility.

Common smells:

- A new date, money, ID, status, validation, auth, or error helper near an existing helper.
- Direct SQL or direct API calls in a layer that normally uses repositories, clients, or services.
- Local validation copied into a screen or endpoint when a schema/domain validator exists.
- Constants, enum values, config keys, routes, or event names redefined in a second place.
- New test fixtures or builders that duplicate existing test helpers.
- A new file with a generic name such as `utils`, `helpers`, `common`, or `constants` without checking the existing shared locations.

## When Not To Reuse

Do not force reuse when the existing implementation has a different owner, a broader obsolete contract, incompatible side effects, or a frozen compatibility surface.

If intentionally creating a parallel implementation, make the reason explicit:

- existing behavior is kept only for backward compatibility
- new code has a different domain responsibility
- existing implementation will be deprecated and removed
- reuse would couple layers that should stay separate
- performance, security, or operational constraints require separation
