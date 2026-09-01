# QuantForge Specification Index

## Status Values

* Planned
* Draft
* In Progress
* Blocked
* Completed
* Deprecated

## Specifications

| ID | Title | Status | Depends On |
| --- | --- | --- | --- |
| [SPEC-001](SPEC-001-repository-foundation.md) | Repository Foundation | Completed | — |
| [SPEC-002](SPEC-002-market-bar-model.md) | Canonical Market Bar Model | Completed | SPEC-001 |
| [SPEC-003](SPEC-003-csv-market-data-provider.md) | CSV Market Data Provider | Completed | SPEC-002 |
| SPEC-004 | Market Data Validation | Planned | SPEC-002 |
| SPEC-005 | Parquet Storage Layer | Planned | SPEC-003, SPEC-004 |
| SPEC-006 | Dataset Catalog | Planned | SPEC-005 |
| SPEC-007 | Feature Interface | Planned | SPEC-005 |
| SPEC-008 | Feature Registry & Cache | Planned | SPEC-007 |
| SPEC-009 | Strategy Interface | Planned | SPEC-007 |
| SPEC-010 | Portfolio State & Accounting | Planned | SPEC-002 |
| SPEC-011 | Order Domain Model | Planned | SPEC-010 |
| SPEC-012 | Event System | Planned | SPEC-009, SPEC-011 |
| SPEC-013 | Event-Driven Backtest Loop | Planned | SPEC-012 |
| SPEC-014 | Commission Model | Planned | SPEC-013 |
| SPEC-015 | Slippage Model | Planned | SPEC-013 |
| SPEC-016 | Momentum Baseline | Planned | SPEC-007, SPEC-009, SPEC-013 |
| SPEC-017 | Performance Analytics | Planned | SPEC-013 |
| SPEC-018 | Experiment Tracking | Planned | SPEC-013, SPEC-017 |

Additional specifications should be added as architecture becomes concrete.

Do not create dozens of speculative specifications in advance.
