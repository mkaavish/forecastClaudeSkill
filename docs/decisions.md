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

## Phase 2 findings (profiler)

| # | Finding | Consequence |
|---|---|---|
| 14 | STL seasonal strength alone cannot separate noise from weak real seasonality: white noise reaches 0.28, weak real seasonality (amplitude 3, noise 5) 0.34. | A period counts as detected only if an F-test across seasonal positions of the detrended series has p < 0.001 **and** strength ≥ 0.10. Measured over 500 null runs (noise, random walk, trend, level shift, zero-heavy): 0 false positives. Weak real seasonality: 98% detected. Strength is reported as an effect size, p-value as the evidence. |
| 15 | A longer period (168) always "explains" a shorter one (24) it contains, so picking the strongest period mislabels hourly data with a daily pattern. | Primary period = shortest detected (the one a model can use). Longer detected periods are then re-tested after removing the primary's seasonal component; `multiple` is true only if one is still significant. |
| 16 | Kendall's tau trend test flagged **30 of 40 pure random walks** as trending (it assumes independent errors). | A trend is reported only if Kendall **and** a drift t-test on first differences both give p < 0.01, with a ≥ 5% relative change, judged on the seasonally adjusted series. Now ≤ 3/40 on random walks; trend + seasonality still detected on 8/8 seeds. Known limit: a real but weak trend in noisy data can be reported as "none"; the wording is "no statistically distinguishable trend", not "no trend". |
| 17 | Robust STL residuals flagged ~7% of clean Gaussian data as outliers (robust fitting shrinks inlier residuals, so the MAD collapses). | Outlier residuals use non-robust STL (seasonal) or a rolling median (non-seasonal): ~0.1% false positives, 100% recall on 10σ spikes. Outliers are flagged, never removed. |
| 18 | A numeric-looking monotonic integer column ("ID by pattern") is indistinguishable from a real series. | Identifier columns are recognised by name only (Phase 1). |

New CLI flag since Phase 1: `--date-order dmy|mdy` (resolves ambiguous dates).
`forecast profile` prints JSON to stdout with a `status` of `ok`, `needs_input` or `refused`; exit codes 0 / 3 / 4 (2 usage, 1 internal).

## Phase 3 decisions (metrics and backtest planning)

- **sMAPE convention:** 200 * mean(|e| / (|a| + |f|)) in percent (0-200 scale); a period with actual and forecast both zero scores 0. `utilsforecast.losses.smape` omits the factor 2 and the percent scale, so the cross-check test compares against `200 *` its value. MAE, RMSE and MASE agree with utilsforecast exactly.
- **MASE denominator:** mean absolute seasonal-naive error on the training data; undefined (None) for a flat history. Selection (Phase 5) must handle None explicitly, not silently.
- **Plan §6 vs §2.4 reconciled:** §6 said "refuse if h > (n - min_train)/3"; §2.4 said shorten the backtest horizon to a floor. Implemented: use the full horizon when it yields >= 3 windows; otherwise shorten to `(n - min_train)//3` with a `BACKTEST_HORIZON_SHORTENED` warning if that is >= `min(h, max(season_length, ceil(h/2)))`; otherwise refuse (`HORIZON_TOO_LONG`, or `INSUFFICIENT_DATA` when not even a 1-step backtest fits). The refusal message states the maximum horizon history supports.
- **Windows:** expanding train, non-overlapping test blocks of the backtest horizon packed against the end of the series, 3 to 5 windows, `min_train = max(2 * season_length, 24)`. Matches StatsForecast `cross_validation(h=h_bt, n_windows=k, step_size=h_bt)`.
- **Default horizon** (when `--horizon` is omitted): D 28, W 13, M 12, Q 4, hourly 24, business-daily 20, yearly 3, capped to what history can fully back-test (with a `HORIZON_DEFAULT_REDUCED` notice).
- **Model eligibility:** intermittent (>= 30% zeros) -> baselines only; SeasonalNaive only with a detected period; AutoETS and AutoARIMA are fitted without seasonality when the period exceeds 24 (168, 365, 52 are impractically slow there), AutoTheta and SeasonalNaive keep the full period. The cap of 24 is a starting value to benchmark in Phase 4.
- **Constant series** is refused (`CONSTANT_SERIES`) from the profile, before any model runs.
