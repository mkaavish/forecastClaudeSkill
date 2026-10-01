---
description: Forecast a time-series CSV with statistically backtested model selection. Use when the user wants a forecast, projection, or prediction from a dataset.
argument-hint: "<file.csv> [--horizon N] [--target COL]"
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/bin/forecast *)
---

# /forecast

Phase 0 placeholder: the orchestration protocol is written in Phase 8.

Engine check: !`${CLAUDE_PLUGIN_ROOT}/bin/forecast --version`

Always call the engine by absolute path, `${CLAUDE_PLUGIN_ROOT}/bin/forecast`; a bare `forecast` is not on PATH.

Arguments: $ARGUMENTS
