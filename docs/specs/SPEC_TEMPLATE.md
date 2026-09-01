# SPEC-XXX — Title

Status: Proposed
Owner: Paul
Created:
Updated:

## 1. Problem

What problem does this specification solve?

Describe the limitation or missing capability in the current system.

---

## 2. Goal

State exactly what this implementation should accomplish.

The goal should be measurable.

---

## 3. Non-Goals

Explicitly state what will NOT be implemented.

Examples:

* no external API integration;
* no frontend;
* no optimization;
* no minute-level support.

Non-goals prevent scope creep.

---

## 4. Background

Explain relevant domain concepts and existing architecture.

Define terminology required to understand this specification.

Reference related specifications where appropriate.

---

## 5. Functional Requirements

### FR-1

...

### FR-2

...

### FR-3

...

Requirements should describe observable behavior.

---

## 6. Non-Functional Requirements

Examples:

### NFR-1 — Determinism

Identical deterministic inputs must produce identical outputs.

### NFR-2 — Testability

Core behavior must be testable without network access.

### NFR-3 — Type Safety

Public interfaces must contain explicit type annotations.

---

## 7. Proposed API

Describe the expected public interface.

Example:

```python
class MarketDataProvider(Protocol):
    def get_bars(...) -> list[Bar]:
        ...
```

The exact implementation may change during development if the spec is updated first.

---

## 8. Data Model

Define:

* objects;
* schemas;
* fields;
* types;
* units;
* timestamps;
* identifiers.

Document important invariants.

---

## 9. Invariants

List properties that must always remain true.

Examples:

* `high >= low`
* `filled_quantity <= requested_quantity`
* `portfolio_equity = cash + position_market_value`

---

## 10. Edge Cases

Identify cases such as:

* empty input;
* duplicate timestamps;
* missing values;
* invalid values;
* zero volume;
* malformed configuration;
* provider failure;
* unexpected ordering.

---

## 11. Error Handling

Define expected behavior for invalid states.

Specify:

* exception types;
* validation errors;
* logging behavior;
* whether processing stops or continues.

Do not silently ignore financially meaningful errors.

---

## 12. Testing Plan

### Unit Tests

* ...

### Integration Tests

* ...

### Regression Tests

* ...

### Property / Invariant Tests

* ...

Tests should be deterministic unless randomness is explicitly required.

---

## 13. Acceptance Criteria

* [ ] AC-1:
* [ ] AC-2:
* [ ] AC-3:
* [ ] Relevant tests pass.
* [ ] Linting passes.
* [ ] Type checking passes.
* [ ] Documentation is updated.
* [ ] Engineering log is updated when necessary.

---

## 14. Performance Considerations

Does performance matter for this specification?

If yes, define the workload and measurable target.

Do not optimize without a benchmark.

---

## 15. Security / Secrets

State whether the implementation uses:

* API keys;
* credentials;
* external services;
* sensitive configuration.

Secrets must never be committed.

---

## 16. Alternatives Considered

### Option A

...

Advantages:

* ...

Disadvantages:

* ...

### Option B

...

Advantages:

* ...

Disadvantages:

* ...

### Decision

Explain why the selected approach is preferred.

---

## 17. Dependencies

List:

* specifications;
* internal components;
* external packages;
* infrastructure.

New external dependencies require justification.

---

## 18. Implementation Notes

Fill this section during implementation.

Record important deviations or discoveries.

If requirements change materially, update the specification before continuing.

---

## 19. Completion Summary

Status:

Files created:

* ...

Files modified:

* ...

Tests added:

* ...

Commands run:

* ...

Known limitations:

* ...

Follow-up specifications:

* ...

Related engineering-log entries:

* ...
