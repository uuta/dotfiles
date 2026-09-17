---
name: existing-code-first
description: "Find reusable code when adding a responsibility, investigating duplication, or reviewing a parallel implementation."
---

# Existing Code First

Locate the existing owner before adding a parallel implementation. Use searches already performed in the task; an obvious local edit does not need a repository-wide inventory.

Search with `rg` for domain terms and responsibility names, then inspect promising implementations and their callers. Reuse or extend code whose contract and side effects match. Consolidate or relocate it only when that is necessary for the requested change.

A separate implementation is reasonable when ownership, compatibility, side effects, or coupling make reuse worse. Explain that boundary if it is not obvious. Similar syntax alone does not establish a shared responsibility.

During review, report duplication only when it creates a concrete correctness, consistency, or maintenance problem in the changed behavior. Name the existing owner and affected callers. Generic filenames, one-off helpers, or an alternative architectural preference alone are not blocking findings.
