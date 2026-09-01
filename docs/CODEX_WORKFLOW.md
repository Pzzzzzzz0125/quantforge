# QuantForge Codex Workflow

This document defines the standard workflow for implementing QuantForge tasks using Codex.

## 1. General Principle

Codex should operate on one well-scoped implementation specification at a time.

Avoid prompts such as:

> Build the market-data system.

Prefer tasks such as:

> Implement SPEC-004 — Market Data Validation.

Each task should have explicit requirements, non-goals, acceptance criteria, and tests.

---

## 2. Before Implementation

Codex should read:

1. `AGENTS.md`
2. `docs/PROJECT_SPEC.md`
3. `ARCHITECTURE.md`
4. `docs/ROADMAP.md`
5. `docs/specs/INDEX.md`
6. the relevant implementation spec
7. relevant existing source code and tests

For a new feature, first create its specification from `docs/specs/SPEC_TEMPLATE.md`.

---

## 3. Standard Feature Workflow

For every significant implementation:

1. Inspect existing implementation.
2. Draft or update the specification.
3. Define concrete acceptance criteria.
4. Identify edge cases and invariants.
5. Confirm compatibility with existing architecture.
6. Implement only the specified scope.
7. Add deterministic tests.
8. Run tests.
9. Run linting.
10. Run formatting checks.
11. Run static type checking.
12. Fix failures introduced by the implementation.
13. Record meaningful bugs or decisions in `docs/ENGINEERING_LOG.md`.
14. Update architecture documentation if architecture changed.
15. Update `docs/specs/INDEX.md`.
16. Update spec status.
17. Stop.

Do not automatically begin the next specification.

---

## 4. Standard Codex Prompt

Use the following structure when starting an implementation:

Read `AGENTS.md`, `docs/PROJECT_SPEC.md`, `ARCHITECTURE.md`,
`docs/ROADMAP.md`, `docs/CODEX_WORKFLOW.md`, and
`docs/specs/INDEX.md`.

We are working on:

`[SPEC-ID — TITLE]`

Inspect the existing implementation and all relevant dependencies.

If the spec does not yet exist, create
`docs/specs/[SPEC-ID]-[name].md`
using `docs/specs/SPEC_TEMPLATE.md`.

Before implementation, make the specification concrete by defining:

* problem;
* goal;
* non-goals;
* functional requirements;
* non-functional requirements;
* public API;
* data model;
* invariants;
* edge cases;
* error handling;
* testing plan;
* acceptance criteria;
* performance considerations;
* alternatives considered.

Then implement exactly the approved scope.

Requirements:

1. Do not add unrelated features.
2. Do not silently change financial assumptions.
3. Do not introduce future-data access.
4. Do not bypass established subsystem boundaries.
5. Do not introduce major dependencies without justification.
6. Prefer the smallest correct implementation with clean extension points.
7. Add deterministic tests for acceptance criteria and important edge cases.
8. Log meaningful bugs, fixes, discoveries, and architectural decisions.
9. Update architecture documentation only if architecture actually changes.
10. Do not begin the next specification.

At completion, report:

* files changed;
* design decisions;
* tests added;
* commands run;
* acceptance criteria status;
* known limitations;
* follow-up work.

---

## 5. Bug Workflow

When a bug is discovered:

### Blocking Bug

If it prevents the current specification from being completed:

1. Create an entry in `docs/ENGINEERING_LOG.md`.
2. Assign a bug ID.
3. Record observed and expected behavior.
4. Identify the root cause when possible.
5. Add a regression test.
6. Implement the smallest correct fix.
7. Run relevant tests.

### Non-Blocking Bug

If unrelated to the current specification:

1. Log the bug.
2. Do not perform a large unrelated refactor.
3. Create follow-up work if necessary.

Do not silently fix meaningful financial bugs.

---

## 6. Scope Control

Codex should not:

* scaffold large future subsystems;
* create unused abstractions;
* redesign unrelated components;
* add UI work during infrastructure tasks;
* add machine learning during data-layer tasks;
* add performance complexity before profiling;
* replace custom core infrastructure with a third-party framework unless explicitly specified.

---

## 7. Completion Checklist

Before completion:

* [ ] Relevant specification exists.
* [ ] Requirements are implemented.
* [ ] Acceptance criteria pass.
* [ ] Unit tests pass.
* [ ] Integration tests pass where applicable.
* [ ] Regression tests exist for fixed bugs.
* [ ] Ruff passes.
* [ ] Formatting passes.
* [ ] Type checking passes.
* [ ] Documentation is current.
* [ ] Engineering log is updated where appropriate.
* [ ] No secrets are committed.
* [ ] Git diff contains no unrelated changes.

---

## 8. Human Review

The developer should review:

* the specification;
* public APIs;
* architectural changes;
* financial assumptions;
* new dependencies;
* tests;
* final `git diff`.

Codex implementation should not replace understanding of the underlying quantitative or computer-science concepts.
