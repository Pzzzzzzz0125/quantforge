# QuantForge Architecture

Status: Early Development

This document describes the architecture that currently exists or has been explicitly approved.

It should not describe speculative implementation as though it already exists.

## 1. Target Data Flow

External Market Data
↓
Market Data Provider
↓
Validation / Normalization
↓
Research Data Storage
↓
Feature Engine
↓
Strategy
↓
Portfolio Construction
↓
Order Manager
↓
Execution Simulator
↓
Fill Events
↓
Portfolio Accounting
↓
Analytics
↓
Experiment Tracking

---

## 2. Major Components

### Market Data

Responsible for:

* retrieving historical data;
* normalizing provider-specific formats;
* validating records;
* preserving raw data;
* providing reproducible research datasets.

### Feature Engine

Responsible for:

* computing reusable research features;
* enforcing temporal correctness;
* tracking dependencies;
* caching immutable results;
* versioning feature definitions.

### Strategy Layer

Responsible for:

* consuming information available at the current simulation timestamp;
* producing signals or desired exposures.

Strategies do not manage orders, cash, commissions, or fills.

### Portfolio Layer

Responsible for:

* translating strategy intent into target positions;
* position sizing;
* portfolio constraints;
* capital allocation;
* risk constraints.

### Order Layer

Responsible for:

* translating target positions into orders;
* validating requested orders;
* managing order lifecycle.

### Execution Layer

Responsible for:

* determining fills;
* commissions;
* slippage;
* liquidity constraints;
* execution timing.

### Accounting Layer

Responsible for:

* cash;
* holdings;
* cost basis;
* realized P&L;
* unrealized P&L;
* marked portfolio value;
* exposure.

### Analytics Layer

Responsible for:

* returns;
* risk metrics;
* drawdowns;
* trade analytics;
* portfolio analytics;
* benchmark comparison.

### Experiment Layer

Responsible for:

* run identity;
* configuration snapshots;
* dataset version;
* source-code version;
* parameter tracking;
* metrics;
* reproducibility.

---

## 3. Dependency Rules

Higher-level research code may depend on stable domain interfaces.

Provider-specific implementations must not propagate into research code.

Strategies must not depend directly on:

* Parquet;
* DuckDB;
* broker APIs;
* commission implementations;
* slippage implementations.

Execution must not depend on strategy-specific logic.

Analytics should consume recorded portfolio and execution state rather than mutate it.

---

## 4. Architectural Principles

### Separation of Concerns

Research, portfolio construction, execution, and accounting are independent concerns.

### Temporal Safety

Information available at timestamp `t` must not depend on information from a timestamp later than `t`.

### Reproducibility

An experiment should be identifiable by its:

* data version;
* code version;
* configuration;
* parameters;
* random seed where applicable.

### Auditability

Important portfolio changes should be explainable through recorded events and fills.

### Replaceable Adapters

External services should be accessed through interfaces so implementations can be replaced.

### Correctness Before Optimization

Performance changes occur only after profiling and must preserve validated behavior.

---

## 5. Initial Technology Direction

Expected initial stack:

* Python
* pytest
* Ruff
* mypy
* Parquet
* DuckDB
* NumPy / Pandas or Polars when justified by later specs

Potential later additions:

* FastAPI
* React / Next.js
* C++
* pybind11
* minute-level market data
* limit-order-book simulation

These technologies should not be introduced until required by an approved specification.

---

## 6. Current Status

SPEC-001 established the Python 3.12 `src/` package, test/lint/type-check toolchain, CI, and standard-library structured logging.

The repository currently has no runtime dependencies and no implemented financial subsystem.

No financial subsystem should be considered implemented until its corresponding specification is completed and tested.
