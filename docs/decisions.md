# Decisions and Phase 0 findings

Measured 2026-09-30 with Claude Code CLI 2.1.119, statsforecast 2.1.1, uv 0.12.21, CPython 3.12.

## Approved decisions (plan §16)
All 13 recommendations approved. License chosen: MIT (plan left MIT vs Apache-2.0 open).
Plugin `forecast`, marketplace `forecast-skill`, distribution `claude-forecast`, import `forecast`.

## Findings that change the plan

| # | Finding | Consequence |
|---|---|---|
| 1 | Plugin skill in `skills/forecast/` is invoked as **`/forecast:forecast`**. A root-level `SKILL.md` was **not loaded at all** on this CLI. | Decision 1: accept `/forecast:forecast`. README documents it. |
| 2 | Plugin `bin/` is **not on PATH** for either the Bash tool or the `` !`…` `` injection (`command not found: forecast`). Docs say it should be; not true for `--plugin-dir` on 2.1.119. | The skill always calls `${CLAUDE_PLUGIN_ROOT}/bin/forecast` by absolute path. `${CLAUDE_PLUGIN_ROOT}` is substituted in injection, `allowed-tools` and the body. Verified end to end. |
| 3 | **`uv` is not installed** on the dev machine and system Python is 3.9 (< 3.10). | `bin/forecast` fails with a clear message (exit 127) if `uv` is missing. README must list `uv` as the one prerequisite; uv fetches Python ≥ 3.10 itself. |
| 4 | `uv run --project <root>` works with venv at `~/.cache/claude-forecast/venv` (override `FORECAST_VENV`). Warm start 0.12 s. Stack installs in ~12 s with warm uv cache; venv ≈ 380 MB. | Decision 7 (uv wrapper) confirmed. |
| 5 | **statsforecast 2.1.1 has no numba dependency.** First `import statsforecast` took ~14 s (cold bytecode), then fast. 6 models × 4 windows × h=28 on 400 daily rows: ~3.8 s. | Plan risk 4 (JIT cold start) downgraded to "slow first import". Still print a progress note. |
| 6 | `StatsForecast(models, freq, n_jobs, fallback_model, verbose)` — `fallback_model` exists. | We still isolate failures per model ourselves (a fallback hides which model failed). |
| 7 | `y` with NaN → `ValueError: This function does not handle missing values`. | Loader must impute/refuse before the engine. |
| 8 | **Missing timestamps are silently accepted**: rows are treated as consecutive, shifting the seasonal phase. | Regularizing to a full calendar index is mandatory, not optional. Needs a regression test. |
| 9 | Short series (10 obs) do not raise for ETS/ARIMA/Theta/SeasonalNaive; they return finite output. | Eligibility rules must come from us (min length), not from model errors. |
| 10 | Constant series: all models return the constant with zero-width intervals. | Profiler flags constant; run is refused. |
| 11 | `cross_validation(level=[80])` yields native `-lo-80/-hi-80` columns for all six models. `forecast(level=[80,95])` yields both levels. | Coverage can be measured from CV without ConformalIntervals. |
| 12 | `claude plugin validate` rejects top-level `description` in marketplace.json (needs `metadata.description`). Marketplace add + install from a local path works (tested with an isolated `CLAUDE_CONFIG_DIR`). | Manifests fixed. Install from the GitHub URL is verified after the first push. |
| 13 | PyPI: `forecast` is taken (200); `claude-forecast` is free (404). | Decision 8 confirmed. |

## Still unverified
- Marketplace install from `mkaavish/forecastClaudeSkill` on GitHub (needs the push).
- Behaviour on newer CLI versions (docs cite v2.1.265+; installed is 2.1.119). Root-skill naming and `bin/` PATH may differ there; our design does not depend on either.
