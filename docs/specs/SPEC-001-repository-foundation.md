# Specification: SPEC-001 — Repository Foundation

## Status

Implemented

## Context

QuantForge needs a small, reproducible engineering baseline before any financial domain work begins. This specification establishes how the Python package is built, checked, tested, and run in continuous integration. It intentionally defines only repository infrastructure and one concrete cross-cutting capability: structured application logging.

## Goals

- Provide an installable Python 3.12 package using the `src/` layout.
- Centralize package metadata, build configuration, and developer-tool configuration in `pyproject.toml`.
- Establish pytest, Ruff, and mypy as the test, lint/format, and type-check tools.
- Provide structured JSON logging using only the Python standard library.
- Preserve explicit directories for tests, benchmarks, configuration, and sample data.
- Run deterministic, network-independent project checks in GitHub Actions after dependencies are installed.
- Verify the installed `quantforge` package imports and exposes version metadata.

## Non-goals

- Market-data ingestion or integration with external data providers.
- Trading strategies, signals, orders, execution, or broker integrations.
- Portfolio construction, accounting, performance, or risk calculations.
- Backtesting or simulation functionality.
- Dataframe, database, web API, or machine-learning foundations.
- Placeholder modules or abstractions for future financial subsystems.
- Packaging and publishing QuantForge to a public package index.

## Design

### Chosen tooling

- Python 3.12 is the minimum and CI target. No known foundation requirement needs an older runtime.
- Hatchling is the PEP 517 build backend because it supports a concise `src/`-layout configuration.
- pytest runs offline unit and smoke tests.
- Ruff performs linting and formatting checks.
- mypy performs strict static type checking of `src/` and `tests/`.
- The standard-library `logging` package supplies logging. A small QuantForge formatter emits one JSON object per record, avoiding another runtime dependency.
- GitHub Actions runs the same explicit checks documented for local development.

All development tools are version-pinned in the `dev` optional dependency group so CI and local environments resolve the same tool versions. QuantForge has no runtime dependencies for this specification.

### Directory structure

```text
.
├── .github/workflows/ci.yml
├── benchmarks/
├── configs/
├── data/
│   ├── processed/
│   ├── raw/
│   └── sample/
├── docs/specs/
├── examples/
├── src/quantforge/
│   ├── __init__.py
│   └── logging.py
├── tests/
│   ├── test_logging.py
│   └── test_smoke.py
└── pyproject.toml
```

Empty working directories contain `.gitkeep` files. Raw and processed data contents remain ignored; small redistributable sample fixtures may be committed under `data/sample/`.

### Package and version metadata

The distribution and import package are both named `quantforge`. The initial version is `0.1.0` and is available as `quantforge.__version__`. Project metadata declares Python `>=3.12`.

### Structured logging

`quantforge.logging` provides:

- a JSON formatter with UTC timestamp, severity, logger name, and rendered message fields;
- exception text when exception information exists; and
- an idempotent logging configuration function with an explicit log level.

The utility writes to standard error through a stream handler and does not configure logging merely by importing `quantforge`.

### Development commands

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy src tests
```

### Testing expectations

- Tests must run without credentials, internet access, mutable external services, or ordering dependencies.
- A smoke test imports `quantforge` and verifies its public version metadata.
- Unit tests cover the structured logging output and configuration behavior.
- Behavior changes made after SPEC-001 require corresponding tests under `tests/`.

### CI behavior

On every push and pull request, one Ubuntu job:

1. checks out the repository;
2. installs Python 3.12;
3. installs the package with its pinned development tools; and
4. runs pytest, Ruff lint, Ruff format checking, and mypy as separate fail-fast steps.

Tests and checks themselves do not access the network. The only required network activity is GitHub Actions setup and dependency installation.

## Acceptance criteria

- [x] `pyproject.toml` defines an installable `src/`-layout package requiring Python 3.12 or newer.
- [x] Package metadata defines version `0.1.0`, and `quantforge.__version__` exposes it.
- [x] Runtime dependencies are empty; development dependencies contain only Hatchling, pytest, Ruff, and mypy as required by their roles.
- [x] pytest discovers and passes an offline package import smoke test.
- [x] Ruff lint and format checks pass.
- [x] mypy passes in strict mode for `src/` and `tests/`.
- [x] Structured logging emits valid JSON with the documented core fields and is covered by offline tests.
- [x] Test, benchmark, configuration, and sample-data directories are present.
- [x] `.gitignore` excludes secrets, Python/build artifacts, environments, and non-sample working data.
- [x] `.env.example` documents supported non-secret environment settings without containing credentials.
- [x] GitHub Actions runs tests, linting, formatting, and type checking on pushes and pull requests using Python 3.12.
- [x] No financial, data, web, or machine-learning subsystem or dependency is introduced.
- [x] The specification index and engineering log record SPEC-001.

## Validation

Run:

```bash
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy src tests
```

Review the dependency metadata and repository tree to confirm the absence of finance libraries and speculative subsystem scaffolding.
