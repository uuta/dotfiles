---
name: refactoring
description: "Refactor an identified area to simplify ownership or duplication while preserving its behavior and existing architecture."
---

# Refactoring

Simplify the identified area while preserving its observable behavior. Keep the repository's architecture unless the request includes changing it.

Locate the behavior's owner, callers, and relevant checks. Prefer deleting unnecessary logic or consolidating a shared responsibility over adding abstractions. Before adding normalization or preprocessing, verify whether the downstream layer already handles the input; repeated transformations and fallbacks that nearly always fire can indicate a wrong assumption.

Extract a helper or component when it gives a coherent responsibility a useful name or centralizes behavior that must stay consistent. Avoid wrappers that merely rename a constructor or split a readable flow. Similar code with different contracts need not share an abstraction.

Use domain services and value objects where the project already follows that architecture. Do not introduce DDD layers, schema changes, early-return rewrites, or performance work merely because a refactor touches a file.

Use existing behavioral tests to establish preservation. Add a focused test when a material behavior is otherwise unprotected; do not require all possible input combinations or new tests for mechanical changes. Run relevant checks after editing and widen only for an identified risk or project requirement.
