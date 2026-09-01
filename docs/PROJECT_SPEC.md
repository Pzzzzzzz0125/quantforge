# QuantForge Project Specification

Status: Active
Version: 0.1

## 1. Mission

QuantForge is a modular quantitative research, portfolio construction, backtesting, and execution-simulation platform.

It supports the complete historical research lifecycle:

Market Data
→ Validation
→ Feature Computation
→ Signal Generation
→ Portfolio Construction
→ Order Generation
→ Execution Simulation
→ Portfolio Accounting
→ Performance Analysis
→ Reproducible Experiment Tracking

The primary engineering objective is to build reliable research infrastructure similar in spirit to tools quantitative developers build for researchers.

The primary research objective is to conduct statistically defensible experiments rather than maximize historical returns.

---

## 2. Target Users

### Quantitative Researcher

Needs to:

* access clean historical data;
* define reusable features;
* implement strategies;
* run historical experiments;
* construct portfolios;
* compare research runs;
* perform walk-forward evaluation;
* evaluate risk and transaction costs.

### Quantitative Developer

Needs to:

* maintain reliable data infrastructure;
* expose reusable APIs;
* provide deterministic backtesting;
* maintain execution simulation;
* ensure reproducibility;
* improve throughput;
* enforce correctness.

---

## 3. Initial Market Scope

### Asset Class

U.S. equities and ETFs.

### Initial Frequency

Daily OHLCV bars.

### Later

Minute bars.

### Stretch

Tick and limit-order-book data.

### Initial Universe

Approximately:

* 30–50 liquid U.S. equities across several sectors;
* 5–10 ETFs for portfolio-level research.

The platform must not depend on one specific stock.

---

## 4. Core Systems

### 4.1 Market Data Layer

Responsibilities:

* provider abstraction;
* historical ingestion;
* incremental synchronization;
* raw-data preservation;
* canonical market-data schemas;
* data validation;
* duplicate detection;
* missing-data detection;
* timestamp normalization;
* corporate-action awareness;
* research-ready storage;
* dataset versioning.

Initial planned storage:

* Parquet
* DuckDB

---

### 4.2 Feature Engine

Responsibilities:

* reusable feature definitions;
* feature registration;
* dependency management;
* time-safe computation;
* caching;
* feature versioning.

Initial features may include:

* simple returns;
* log returns;
* rolling returns;
* momentum;
* moving averages;
* rolling volatility;
* rolling correlation;
* liquidity measures.

Research-specific features may later include:

* spread;
* z-score;
* beta;
* cointegration statistics;
* residual returns;
* estimated mean-reversion half-life.

---

### 4.3 Strategy Layer

A strategy consumes information available at the current simulation timestamp and produces research intent.

Possible outputs:

* signals;
* scores;
* target exposures;
* target portfolio weights.

A strategy must not directly modify:

* cash;
* holdings;
* orders;
* fills;
* commissions;
* slippage.

---

### 4.4 Portfolio Engine

Responsibilities:

* signal-to-position translation;
* position sizing;
* capital allocation;
* target weights;
* portfolio constraints;
* risk constraints.

Initial methods:

* equal weight;
* signal-proportional weight;
* inverse-volatility weight.

Later:

* risk parity;
* mean-variance optimization;
* turnover constraints;
* sector constraints.

---

### 4.5 Event-Driven Backtesting Engine

Target lifecycle:

MarketEvent
→ SignalEvent
→ Portfolio Decision
→ OrderEvent
→ FillEvent
→ Portfolio Update

The engine must make execution timing explicit.

The engine must prevent strategies from using future information.

---

### 4.6 Execution Simulator

Initial functionality:

* market orders;
* deterministic commission model;
* configurable slippage;
* explicit execution timing.

Later:

* limit orders;
* partial fills;
* volume participation constraints;
* spread modeling;
* market-impact approximations.

Stretch:

* C++ limit-order-book and matching engine.

---

### 4.7 Portfolio Accounting

Track:

* cash;
* position quantity;
* average cost;
* market value;
* realized P&L;
* unrealized P&L;
* portfolio equity;
* gross exposure;
* net exposure.

Accounting correctness must be covered by deterministic tests and explicit invariants.

---

### 4.8 Analytics

Initial metrics:

* cumulative return;
* annualized return;
* annualized volatility;
* Sharpe ratio;
* maximum drawdown;
* turnover;
* trade count;
* transaction costs.

Later:

* Sortino ratio;
* Calmar ratio;
* beta;
* alpha;
* tracking error;
* information ratio;
* contribution analysis;
* rolling metrics;
* portfolio concentration.

---

### 4.9 Experiment Tracking

Every meaningful experiment should capture:

* experiment ID;
* Git commit;
* dataset version;
* universe;
* date range;
* feature versions;
* strategy version;
* strategy parameters;
* portfolio parameters;
* execution assumptions;
* commission assumptions;
* slippage assumptions;
* random seed where applicable;
* performance metrics.

Historical experiments should be reproducible.

---

## 5. Research Modules

### R1 — Cross-Sectional Momentum Baseline

Purpose:

Validate the infrastructure using a transparent and interpretable strategy.

The initial baseline is not intended to demonstrate proprietary alpha.

---

### R2 — Statistical Arbitrage / Relative Value

Research topics:

* rolling correlation;
* cointegration;
* stationarity;
* spread construction;
* z-score;
* mean reversion;
* mean-reversion half-life;
* relative-value signals.

The implementation should distinguish correlation from cointegration.

---

### R3 — ML-Assisted Statistical Arbitrage

Research question:

Can machine learning distinguish temporary mean-reverting deviations from structural relationship breakdowns?

Initial models:

* logistic regression;
* decision tree.

More complex models should only be introduced when justified.

Evaluation should emphasize out-of-sample performance rather than training accuracy.

---

### R4 — Dynamic Asset Allocation

Research question:

Can risk-aware dynamic allocation improve risk-adjusted performance compared with static portfolio allocation?

Initial portfolio universe may include broad ETFs representing:

* U.S. equities;
* growth / technology;
* small caps;
* Treasury bonds;
* gold;
* commodities.

Methods may include:

* equal weighting;
* inverse volatility;
* risk parity;
* momentum-aware allocation.

---

### R5 — Execution Research

Later research question:

How do different execution methods change realized trading cost and portfolio performance?

Potential methods:

* immediate market execution;
* TWAP;
* VWAP;
* participation-based execution.

---

## 6. Research Integrity Requirements

QuantForge should explicitly protect against or document:

* look-ahead bias;
* data leakage;
* survivorship bias;
* unrealistic execution assumptions;
* ignored transaction costs;
* repeated test-set optimization;
* cherry-picked reporting;
* unstable parameters.

Machine-learning experiments must use time-aware splitting.

Walk-forward evaluation should eventually be supported.

Gross and net performance should be distinguished.

---

## 7. Performance Philosophy

Correctness comes first.

Once correctness is established, benchmark:

* market-data loading;
* feature computation;
* event processing;
* experiment execution;
* parameter sweeps.

Potential optimization techniques may later include:

* feature caching;
* vectorized computation;
* Parquet predicate pushdown;
* parallel experiment execution;
* compiled performance-critical components.

Performance claims must be produced by repeatable benchmarks.

---

## 8. Interfaces

Initial primary interfaces:

* Python library;
* command-line interface.

Later:

* REST API;
* web dashboard.

The frontend must remain a control and visualization layer only.

---

## 9. Definition of Project Success

A successful repository should eventually allow another developer to:

1. Clone the repository.
2. Install dependencies.
3. Load deterministic sample market data.
4. Run a baseline backtest.
5. Inspect generated orders and fills.
6. Verify portfolio accounting.
7. Reproduce reported metrics.
8. Add a strategy without modifying the backtesting core.
9. Compare experiments.
10. Run the full test suite.
11. Understand important design decisions through documentation.
12. Reproduce published benchmark results.
