# QuantForge

QuantForge is a modular quantitative research, portfolio construction, backtesting, and execution-simulation platform.

The project is designed around a full quantitative research workflow:

**Market Data → Validation → Features → Signals → Portfolio Construction → Orders → Execution → Accounting → Analytics → Experiments**

The primary goal is not to produce investment recommendations or maximize historical returns. The goal is to build reliable quantitative research infrastructure with strong guarantees around correctness, reproducibility, testability, and realistic simulation.

## Planned Capabilities

### Research Infrastructure

* Historical U.S. equity and ETF market-data ingestion
* Data validation and normalization
* Versioned Parquet storage
* DuckDB analytical queries
* Reusable feature computation
* Feature caching and dependency tracking
* Pluggable strategy interface
* Reproducible experiment tracking
* Walk-forward evaluation

### Backtesting & Execution

* Event-driven simulation
* Portfolio accounting
* Market and limit orders
* Commission modeling
* Slippage modeling
* Partial fills
* Liquidity and volume constraints
* Risk and portfolio constraints

### Research Modules

* Cross-sectional momentum baseline
* Statistical arbitrage / pairs trading
* ML-assisted signal filtering
* Dynamic asset allocation
* Execution research

### Stretch Goals

* Minute-level data
* Parallel parameter sweeps
* C++ execution core
* Limit-order-book simulator
* Matching engine
* Python/C++ bindings

## Engineering Principles

1. Correctness before performance.
2. No hidden look-ahead bias.
3. Research logic is separated from execution logic.
4. Every meaningful experiment should be reproducible.
5. Financial state transitions should be auditable.
6. Tests should use deterministic synthetic data whenever possible.
7. Performance improvements must be measured.
8. The web interface must not contain core financial logic.

## Development Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy src tests
```

## Project Status

QuantForge is under active development. SPEC-001 established the repository foundation; financial subsystems remain planned and are not yet implemented.

See:

* [`docs/PROJECT_SPEC.md`](docs/PROJECT_SPEC.md) for the system definition.
* [`docs/ROADMAP.md`](docs/ROADMAP.md) for implementation order.
* [`ARCHITECTURE.md`](ARCHITECTURE.md) for current architecture.
* [`docs/specs/`](docs/specs/) for implementation specifications.
* [`docs/ENGINEERING_LOG.md`](docs/ENGINEERING_LOG.md) for bugs, fixes, decisions, and performance findings.
