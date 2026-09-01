# QuantForge Agent Instructions

## 1. Project Purpose

QuantForge is a quantitative research, portfolio construction, backtesting, and execution-simulation platform.

Its primary purpose is to demonstrate production-quality quantitative engineering.

The project prioritizes:

1. Correctness
2. Prevention of look-ahead bias and data leakage
3. Reproducibility
4. Clear system boundaries
5. Testability
6. Auditability
7. Performance
8. Developer ergonomics
9. UI polish

The project is NOT intended to:

* provide live investment recommendations;
* optimize historical performance at any cost;
* predict a single stock as its primary purpose;
* become a collection of disconnected notebooks;
* hide financial or research logic inside frontend code.

Read `docs/PROJECT_SPEC.md` before implementing major functionality.

Read the relevant specification under `docs/specs/` before modifying a subsystem.

Read `ARCHITECTURE.md` before introducing architectural dependencies.

---

## 2. Core System Boundaries

Maintain the following conceptual flow:

Market Data
→ Validation / Normalization
→ Feature Computation
→ Strategy Signals
→ Portfolio Construction
→ Orders
→ Execution / Fills
→ Portfolio Accounting
→ Analytics
→ Experiment Tracking

These responsibilities must remain separated.

### Strategies must not:

* modify cash directly;
* modify portfolio positions directly;
* perform commission calculations;
* perform slippage calculations;
* access future timestamps;
* depend directly on a database implementation;
* bypass the order/execution system.

### Frontend code must not:

* calculate financial returns;
* perform portfolio accounting;
* generate strategy signals;
* implement trading logic;
* perform feature computation.

### External providers must:

* be accessed through explicit provider interfaces;
* not leak provider-specific objects into core domain logic.

---

## 3. Implementation Workflow

For every non-trivial feature:

1. Read relevant documentation.
2. Inspect existing implementation and dependencies.
3. Create or update a numbered spec under `docs/specs/`.
4. Define requirements and acceptance criteria before implementation.
5. Implement only the specified scope.
6. Add deterministic tests.
7. Run tests, linting, formatting, and type checking.
8. Record meaningful findings in `docs/ENGINEERING_LOG.md`.
9. Update `ARCHITECTURE.md` only if architecture changes.
10. Update `docs/specs/INDEX.md`.
11. Mark the spec complete only after acceptance criteria pass.
12. Stop. Do not automatically begin the next specification.

Do not combine multiple large specifications into one implementation unless explicitly requested.

---

## 4. Specification Rules

Each non-trivial implementation should have a specification such as:

`docs/specs/SPEC-012-event-system.md`

Specifications should define:

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

Do not silently change financial assumptions during implementation.

If a requirement is materially ambiguous, document the chosen interpretation before coding.

---

## 5. Bug Handling

Meaningful bugs must be recorded in `docs/ENGINEERING_LOG.md`.

Each bug entry should include:

* Bug ID
* Date
* Status
* Severity
* Component
* Related spec
* Observed behavior
* Expected behavior
* Root cause
* Fix
* Regression test
* Files changed

Never silently fix a financially meaningful calculation bug.

### When an unrelated bug is discovered:

If it blocks the current implementation:

* log it;
* fix it;
* add a regression test.

If it does not block the current implementation:

* log it;
* do not perform an unrelated refactor.

---

## 6. Testing Requirements

Core financial systems require deterministic unit tests.

Important invariants include:

* portfolio equity = cash + marked value of all positions;
* filled quantity must not exceed requested quantity;
* long-only portfolios must not contain negative positions;
* commissions must not be negative;
* volume-constrained execution must respect participation limits;
* a strategy must never access data later than simulation time;
* zero-cost round trips at equal prices should preserve portfolio equity;
* identical deterministic inputs should produce identical results.

Prefer synthetic datasets for core engine tests.

Unit tests must not require external market-data APIs.

Add regression tests for meaningful bugs.

---

## 7. Research Integrity

Every backtest should explicitly identify:

* universe;
* dataset or dataset version;
* date range;
* feature parameters;
* strategy parameters;
* portfolio parameters;
* execution timing;
* commission assumptions;
* slippage assumptions;
* random seed where applicable;
* benchmark where applicable.

Machine-learning research must use time-aware splits.

Do not randomly shuffle financial time-series observations unless explicitly justified by the relevant spec.

Prevent or explicitly discuss:

* look-ahead bias;
* data leakage;
* survivorship bias;
* unrealistic fills;
* ignored transaction costs;
* repeated optimization on the test set;
* cherry-picked results.

Negative research results must not be hidden.

---

## 8. Code Quality

Primary implementation language: Python.

Use:

* modern Python type hints;
* dataclasses or Pydantic models where appropriate;
* pytest;
* structured logging;
* explicit public interfaces;
* small cohesive modules.

Prefer explicit, readable implementation over clever abstractions.

Do not introduce major dependencies without documenting why they are needed.

Do not optimize before profiling.

Avoid placeholder implementations for future systems.

---

## 9. Documentation Sources of Truth

* Project intent: `docs/PROJECT_SPEC.md`
* Current architecture: `ARCHITECTURE.md`
* Implementation order: `docs/ROADMAP.md`
* Exact feature requirements: `docs/specs/`
* Bugs, fixes, decisions, discoveries: `docs/ENGINEERING_LOG.md`
* Public presentation: `README.md`

If code and documentation disagree, investigate rather than silently changing either.

---

## 10. Definition of Done

Before declaring work complete:

* implementation matches the relevant specification;
* all acceptance criteria are satisfied;
* relevant tests pass;
* linting and type checking pass;
* unrelated files have not been changed;
* meaningful bugs or decisions are logged;
* architecture documentation is updated if necessary;
* no secrets or API keys are committed;
* `git diff` has been reviewed;
* the spec status and index are updated.
