# Engineering Log

## 2026-08-31

- Created the initial QuantForge repository scaffold.
- Accepted and implemented [SPEC-001 — Repository Foundation](specs/SPEC-001-repository-foundation.md).
- Set Python 3.12 as the minimum version and selected Hatchling for the `src/`-layout build.
- Kept runtime dependencies empty. Pinned Hatchling, pytest, Ruff, and mypy as the complete development toolchain.
- Added opt-in structured JSON logging with the Python standard library instead of adding a logging dependency.
- Added a pinned GitHub Actions quality gate for offline tests, linting, formatting, and strict type checking.
- Validated all four checks locally. The available local interpreter was Python 3.14.3; CI provides the required Python 3.12 validation environment.

