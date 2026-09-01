# QuantForge Roadmap

This roadmap describes implementation order.

Individual requirements belong in numbered specifications under `docs/specs/`.

## Phase 0 — Engineering Foundation

* [x] SPEC-001 Repository Foundation
* [x] Python package structure
* [x] Testing
* [x] Linting
* [x] Type checking
* [x] CI
* [x] Documentation structure
* [x] Deterministic sample-data location

Exit condition:

The repository installs cleanly and automated quality checks pass.

---

## Phase 1 — Market Data

Planned areas:

* canonical market bar model;
* CSV provider;
* market-data validation;
* Parquet storage;
* dataset catalog;
* external historical-data provider;
* incremental synchronization;
* data-quality reporting.

Exit condition:

Historical data can be ingested, validated, stored, queried, and reproduced.

---

## Phase 2 — Feature Engine

Planned areas:

* feature interface;
* feature registry;
* rolling time-series features;
* cross-sectional features;
* feature dependencies;
* feature caching;
* feature versioning;
* temporal-safety checks.

Exit condition:

Strategies can request reusable features without accessing future information.

---

## Phase 3 — Backtesting Core

Planned areas:

* market events;
* signals;
* portfolio state;
* target positions;
* orders;
* fills;
* accounting;
* event loop;
* market execution;
* commissions;
* slippage.

Exit condition:

A deterministic strategy can be manually verified end to end.

---

## Phase 4 — Baseline Research

Planned areas:

* cross-sectional momentum strategy;
* benchmark support;
* performance analytics;
* experiment tracking;
* reproducible configuration.

Exit condition:

A complete research experiment can be reproduced from saved configuration.

---

## Phase 5 — Statistical Arbitrage

Planned areas:

* pair candidate generation;
* rolling correlation;
* cointegration;
* spread construction;
* z-score;
* stationarity analysis;
* mean-reversion baseline;
* long-only relative-value variant;
* walk-forward evaluation.

---

## Phase 6 — ML Signal Research

Planned areas:

* supervised dataset generation;
* logistic-regression baseline;
* decision tree;
* time-aware validation;
* ML signal filtering;
* baseline-versus-ML comparison;
* robustness testing.

---

## Phase 7 — Portfolio Research

Planned areas:

* ETF universe;
* equal-weight portfolio;
* inverse-volatility allocation;
* risk parity;
* momentum-aware allocation;
* diversification analytics;
* portfolio constraints.

---

## Phase 8 — Advanced Execution

Planned areas:

* limit orders;
* partial fills;
* volume constraints;
* execution-cost attribution;
* TWAP;
* VWAP;
* participation-based execution;
* execution research.

---

## Phase 9 — Performance Engineering

Planned areas:

* profiling;
* feature-computation benchmarks;
* data-loading benchmarks;
* parallel parameter sweeps;
* cache optimization;
* memory profiling;
* regression benchmarks.

---

## Phase 10 — Advanced / Stretch

Potential areas:

* minute-level data;
* C++ execution core;
* Python/C++ bindings;
* limit-order-book representation;
* price-time-priority matching;
* matching-engine benchmarks;
* market microstructure research.

---

## Roadmap Rules

Do not begin a later phase merely because it is more interesting.

Correctness dependencies take priority.

Do not implement a roadmap item without a corresponding specification when the change is non-trivial.

The roadmap may change as engineering discoveries are made, but changes should be deliberate and documented.
