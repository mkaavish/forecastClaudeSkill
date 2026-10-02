# Changelog

## 0.2.0

- **Dashboard.** Every run now also writes `dashboard.html`: a self-contained interactive page
  (headline figures, forecast chart with 80%/95% intervals and hover details, model comparison,
  per-window error, backtest scores, warnings). The engine builds it from its own results, so it
  shows only engine numbers. It follows light/dark themes and works at phone width.
- The Claude skill publishes the dashboard as an Artifact and puts the link at the top of its answer.
- New warning code `DASHBOARD_FAILED` (a failed dashboard never loses the forecast).
- Plugin version bumped so existing installs pick the update up.

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
