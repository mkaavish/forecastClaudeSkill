# Changelog

## 0.1.0

First release.

- `forecast` engine: CSV ingestion with date/target/frequency detection, data profiling,
  rolling-origin backtesting of Naive, SeasonalNaive, HistoricAverage, AutoETS, AutoTheta and
  AutoARIMA, deterministic model selection (MASE with a 5% parsimony margin over the best baseline),
  prediction intervals with backtest-based widening, chart, and a plain-text summary.
- Statistical-integrity checks: 33 catalogued warning codes and 12 refusal codes, each tested.
- Claude Code plugin: the `/forecast:forecast` skill, with an ask-never-guess protocol for
  ambiguous datasets.
- Five synthetic example datasets, 590+ tests, and a live skill evaluation harness.
