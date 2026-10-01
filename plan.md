# `/forecast` — Implementation Plan

> Status: **planning only, no code written.** Awaiting approval of the decisions in §16.

An autonomous forecasting analyst for Claude Code: time-series dataset → validation → rolling-origin backtest of several models → deterministic model selection → forecast → plain-English analysis.

**Philosophy:** LLM reasoning + deterministic statistical computation. Claude = analyst/orchestrator. Python = statistical engine.

Repo: https://github.com/mkaavish/forecastClaudeSkill

**Research caveats.** Claude Code docs were read via fetch agents; some pages were truncated and those findings rest on summaries. Existing GitHub skills were reviewed from listings only, not code. Items marked "Phase 0 verifies" are tested before anything depends on them.

---

## 1. Research findings

### Claude Code (current docs)
- **Skills replace commands.** `.claude/commands/` is legacy ("Custom commands have been merged into skills"). New work uses `skills/<name>/SKILL.md`.
- **SKILL.md frontmatter** includes `description`, `argument-hint`, `arguments`, `disable-model-invocation`, `allowed-tools`, `when_to_use`, `model`, `effort`.
- **Arguments:** `$ARGUMENTS`, `$0`, `$1`, named `$arg`.
- **Plugin layout:** `.claude-plugin/plugin.json` (only `name` required), `skills/`, `bin/`, `hooks/`, etc.
- **`bin/` executables** are on the Bash tool's PATH while the plugin is enabled.
- **Env vars:** `${CLAUDE_PLUGIN_ROOT}` / `${CLAUDE_PLUGIN_DATA}` are substituted inline in SKILL.md bodies; they are *not* in the Bash environment.
- **Python dependencies:** no Python-specific mechanism. The `dependencies` field only declares other plugins. Documented pattern: a SessionStart hook installing into `${CLAUDE_PLUGIN_DATA}` (shown for npm).
- **Distribution:** `.claude-plugin/marketplace.json` in the same repo (`"source": "./"`). Users run `/plugin marketplace add mkaavish/forecastClaudeSkill` then `/plugin install <plugin>@<marketplace>`.
- **Local dev:** `claude --plugin-dir ./`, `/reload-plugins`, `claude plugin validate`.
- **Dynamic context injection:** `` !`cmd` `` runs a command before Claude sees the skill body.
- **Naming problem:** plugin skills are namespaced (`/forecast:forecast`). Docs never show a plugin skill invoked as bare `/forecast`. A single-skill plugin with root `SKILL.md` might. Phase 0 settles this.

### StatsForecast (PyPI: 2.1.1, Python ≥ 3.10)
- Long-format input (`unique_id`, `ds`, `y`). `StatsForecast(models, freq, n_jobs)`.
- `cross_validation(h, df, n_windows, step_size, test_size, input_size, level, refit, prediction_intervals)` returns `cutoff`, `ds`, `y`, one column per model; intervals as `{model}-lo-80` / `-hi-80`.
- Models: `Naive`, `SeasonalNaive`, `HistoricAverage`, `AutoETS`, `AutoARIMA`, `AutoTheta`, `MSTL`, intermittent family (`CrostonOptimized`, `ADIDA`, `IMAPA`, `TSB`).
- Native intervals for Naive, SeasonalNaive, AutoETS, AutoARIMA, AutoTheta. `ConformalIntervals(h, n_windows)` can replace them; requires `n_windows × h < series length`.
- **Not confirmed:** `fallback_model`, minimum series length, NaN/missing-timestamp handling (docs say `y` must be clean — we regularize ourselves). Theta signature unread. Numba cold-start cost is inferred, not read.

### Existing skills
- Generic forecasting skills exist (e.g. jeremylongshore's "Forecasting Time Series Data" — ARIMA/Prophet, mostly prompt-driven; a TimesFM skill) and a Nixtla plugin that runs StatsForecast/MLForecast/NeuralForecast.
- Differentiators to aim for (verify by reading those repos): standalone deterministic engine; baseline-first selection; ability to refuse; ambiguity protocol; interval-calibration checks; known-truth tests.

---

## 2. Problems in the original proposal

1. **sMAPE as default selection metric is a poor choice** — unstable/undefined near zero, asymmetric, breaks on zero-heavy demand. **Use MASE** (MAE scaled by in-sample seasonal-naive MAE): scale-free, zero-safe, aggregates across windows, built-in baseline reading (<1 beats seasonal naive). Report MAE/RMSE/sMAPE as secondary.
2. **Summing interval bounds for a 30-day total is wrong** (errors are correlated; StatsForecast gives no joint sample paths). V1 reports the aggregate **point** forecast only; an aggregate interval only if estimable empirically from backtest window-total errors with enough windows.
3. **"Lowest mean error wins" is noisy** with 3–5 windows. Use a deterministic margin rule: a non-baseline model must beat the best baseline by ≥ δ (start 3%, tune on synthetic data), else the baseline wins. Ties break by fixed simplicity order.
4. **Backtest horizon must equal forecast horizon.** If history can't give ≥ 3 windows at full h, shrink the backtest horizon to a floor and warn; if impossible, refuse to select.
5. **Model-based intervals usually under-cover.** Measure empirical coverage of the 80% interval in CV; warn if badly off; use conformal when data allows.
6. **Don't silently forecast through ambiguity.** Missing timestamps may mean "unobserved" or "zero sales" → explicit fill policy; Claude asks when genuinely ambiguous.
7. **Annual seasonality (365) on daily data** isn't practical for ETS/ARIMA. V1: single `season_length` from frequency-based candidates, confirmed by STL seasonal strength. Multiple seasonality is flagged, not modelled (MSTL is V2).
8. **Non-negative targets:** clip lower bound at 0, disclosed.
9. **Intermittent demand:** profiler flags it; V1 runs baselines only with a warning (models are V2).
10. **Structural breaks:** not modelled in V1; warn when the latest backtest windows are much worse than earlier ones.
11. **Overlooked, added to V1:** date-parsing ambiguity (`01/02/2026`), CSV delimiters/encodings, `schema_version` in every JSON, run metadata (library versions, seed, timing), machine-readable exit codes, `needs_input` status, first-run numba latency, Claude reading only the profile (never raw rows) for privacy and token cost.

### Structure review of the proposed tree
- Use a `src/` layout (`src/forecast/`).
- No `forecasting.py` inside package `forecast` → `pipeline.py`.
- No `warnings.py` (shadows stdlib name) → `diagnostics.py`.
- Split by lifecycle, not by check type: `loading.py` (read, detect, regularize) + `profile.py` (statistics) instead of `profiler.py` + `validation.py`.
- Keep `metrics.py` separate (pure functions, easy to test). Add `selection.py` — the selection rule is the core of the project.
- Skill is thin (short SKILL.md + two references loaded on demand); the Python package is the product.

---

## 3. V1 scope and user experience

**In V1:** one series per run; single CSV; Naive, SeasonalNaive, HistoricAverage, AutoETS, AutoARIMA, AutoTheta; rolling-origin backtest; deterministic selection; warnings and refusals; forecast + intervals + chart; standalone CLI + Claude skill; demo data; tests.

**Out of V1:** grouped/multi-series, holidays, regressors, Excel/Parquet, intermittent models, hierarchical, ML models. Internal data is long-format with a `series` id so grouped forecasting can be added without breaking contracts.

**UX:** `/forecast sales.csv --horizon 30` prints a short report. For `date,store,product,units_sold,inventory,price`, Claude lists the readings (total / per store / per product) and asks; V1 then runs the chosen one.

---

## 4. Architecture and execution flow

**Claude:** parses intent → calls `forecast profile` → reads profile and `ambiguities` → asks when more than one reading is reasonable → calls `forecast run` with explicit args → explains results (observed vs forecast vs interpretation). Never computes statistics; never picks the winner.

**Python:** everything numerical, plus model selection.

**Flow for `/forecast sales.csv`:**
1. SKILL.md invokes `forecast profile sales.csv`.
2. If `ambiguities` non-empty, Claude asks the user.
3. Claude runs `forecast run sales.csv --target … --date … [--horizon …]`.
4. Python: load → regularize → eligibility (may refuse) → plan windows → cross-validate eligible models → select → refit on full history → forecast → diagnostics → write artifacts.
5. Claude reads `result.json` and writes the analysis.

**Statuses:** `ok`, `ok_with_warnings`, `needs_input`, `refused`. Exit codes: `0`, `0`, `3`, `4`; usage error `2`; internal error `1`.

---

## 5. Profiling and validation

Profiler reports: rows/columns/dtypes; date and target candidates with confidence; candidate dimension columns; inferred frequency (mode of diffs + regularity score); date range, observation count, missing timestamps and gap structure; duplicate timestamps (exact vs conflicting); missing / non-numeric / negative values; zero fraction and intermittency flag; near-constant detection; IQR/MAD outlier counts (flagged, never removed); trend (Theil–Sen slope + Mann–Kendall); STL seasonal strength for frequency-derived candidate periods; `ambiguities[]` (structured questions with options).

**Fill policy:** `--fill interpolate|zero`. Default interpolate when gap share ≤ 10%; above that, refuse. If zero-fill is plausible, Claude asks first.

---

## 6. Models, backtesting, selection, intervals

| Model | Why it exists |
|---|---|
| Naive | Minimum baseline. |
| SeasonalNaive | Seasonal baseline, only when `season_length > 1`. |
| HistoricAverage | Correct baseline for stationary noise; guards against overfitting "no signal". |
| AutoETS | Strong default for trend + seasonality. |
| AutoARIMA | Captures autocorrelation ETS misses; capped for long seasonal periods. |
| AutoTheta | Cheap, robust on short series. Drop if benchmarks show it never wins. |

Each model has an eligibility rule (minimum length, cycles available, intermittency). Registry = one dataclass per model; adding a model is one entry.

**Backtest:** expanding-window rolling origin; `h_backtest = h`; `min_train = max(2·season_length, 24)`; non-overlapping windows (`step = h`), up to 5, minimum 3; a model failing any window is excluded and the failure recorded.

**Selection:**
1. Primary metric: MASE averaged over windows and horizon steps.
2. Compute best baseline first.
3. A non-baseline wins only if it beats that baseline by ≥ δ; otherwise the baseline wins.
4. Ties break by simplicity: Naive < SeasonalNaive < HistoricAverage < AutoETS < AutoTheta < AutoARIMA.
5. Output always states the reason in structured form.

**Intervals:** 80% and 95%; native by default, conformal when `n_windows × h < len`; empirical coverage measured on backtest; lower bound clipped at 0 for non-negative targets.

**Default horizon (if omitted):** D→28, W→13, M→12, Q→4. Refuse if `h > (n − min_train)/3`; warn if `h > n/5`.

---

## 7. Contracts, CLI, outputs

**Contracts:** pydantic v2 models; JSON Schema exported to `schemas/`; every file carries `schema_version`.

```json
// result.json (abridged)
{
  "schema_version": "1",
  "status": "ok_with_warnings",
  "input": {"file": "sales.csv", "date": "date", "target": "sales", "frequency": "D", "n_obs": 1004},
  "backtest": {"horizon": 30, "n_windows": 5, "metric": "mase",
               "models": [{"name": "AutoETS", "mase": 0.61, "mae": 771, "rmse": 1032, "smape": 6.2, "failed_windows": 0}]},
  "selection": {"winner": "AutoETS", "reason": "beat_baseline_by_margin", "baseline": "SeasonalNaive", "margin": 0.22},
  "forecast": {"horizon": 30, "total": 782000, "change_vs_prior": 0.084, "interval_total": null},
  "diagnostics": {"coverage_80": 0.74},
  "warnings": [{"code": "WIDE_INTERVALS", "severity": "warn", "message": "…"}],
  "artifacts": {"forecast_csv": "forecast.csv", "plot": "forecast.png"}
}
```

**Warning catalog (stable codes, thresholds):** `SHORT_HISTORY`, `HORIZON_TOO_LONG`, `MISSING_DATA_HIGH`, `IRREGULAR_SAMPLING`, `NO_SEASONALITY`, `MULTIPLE_SEASONALITY`, `INTERMITTENT`, `BASELINE_WON`, `POOR_BACKTEST` (MASE ≥ 1), `UNSTABLE_ACROSS_WINDOWS`, `LOW_COVERAGE`, `WIDE_INTERVALS`, `RECENT_DEGRADATION`.

**CLI:**
- `forecast profile FILE`
- `forecast run FILE` (also default for `forecast FILE`)
- Flags: `--horizon`, `--target`, `--date`, `--output` (default `./forecast-output/<name>/`), `--fill`, `--where col=value`, `--agg sum|mean`.
- Deferred: `--frequency` (inferred), `--group` (V2).

**Output files:** `profile.json`, `result.json`, `backtest.csv` (per window/model errors), `forecast.csv` (`series, ds, forecast, lo_80, hi_80, lo_95, hi_95, model`), `forecast.png`. `report.md` dropped: Claude writes the narrative; CLI prints a templated text summary.

**Chart:** matplotlib; history, vertical forecast-start line, forecast, shaded 80%/95% bands.

---

## 8. Failure handling and fallbacks

- A single model failure is recorded and excluded; the run continues.
- If all complex models fail, baselines still run with a warning.
- Constant series, insufficient history, or no valid windows → `refused` with reason code; no forecast file.
- Ambiguous input → `needs_input` with structured questions.

---

## 9. Testing

Seeded synthetic generators: linear trend, weekly seasonality, trend + seasonality, white noise, random walk, constant, missing observations, zero-heavy demand, short series, level shift.

Behavioural assertions:
- SeasonalNaive wins on clean seasonal data.
- A baseline wins on white noise (margin rule).
- ETS/Theta beat Naive on trend + seasonality.
- Constant series is refused.
- Metrics match hand-computed values; cross-check with `utilsforecast`.
- Interval coverage on simulated data within tolerance.
- Model failure via monkeypatched exception.
- Selection edge cases: margin, ties, failed windows.
- Golden-file + JSON Schema validation.
- CLI end-to-end on `examples/`.
- Slow tests (numba JIT) behind a pytest marker.

**Demo data (seeded generator script, no copyrighted data):** `retail_sales.csv`, `saas_revenue.csv`, `website_traffic.csv`, `inventory_demand.csv` (zero-heavy), plus a multi-column file demonstrating `needs_input`.

---

## 10. Dependencies, packaging, install

- **Runtime:** `statsforecast`, `pandas`, `numpy`, `matplotlib`, `pydantic`; `scipy`/`statsmodels` transitively (STL via statsmodels). **Dev:** `pytest`, `ruff`. **Python ≥ 3.10.**
- Install size a few hundred MB (numba); document it.
- `pyproject.toml`, `src/forecast`. PyPI name `forecast` likely taken → distribution name like `claude-forecast`, import name `forecast` (Phase 0 checks).
- **Dependency mechanism:** `bin/forecast` wrapper using `uv` (`uv run --project <dir>`; dir resolved from script path); clear error if `uv` missing. Alternative: SessionStart hook creating a venv in `${CLAUDE_PLUGIN_DATA}`. Phase 0 compares.
- **User install:**
  ```
  /plugin marketplace add mkaavish/forecastClaudeSkill
  /plugin install forecast@<marketplace-name>
  ```
- **Standalone:** `uv tool install .` or `pip install .`, then `forecast sales.csv`.

---

## 11. Repository tree

```
forecastClaudeSkill/
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── skills/forecast/
│   ├── SKILL.md                 # thin: orchestration + ambiguity protocol
│   └── references/
│       ├── interpretation.md    # explaining results; facts vs forecasts
│       └── model-selection.md   # selection rule, for accurate citation
├── bin/forecast                 # wrapper (uv)
├── src/forecast/
│   ├── __init__.py  __main__.py  cli.py
│   ├── schema.py                # pydantic contracts
│   ├── loading.py               # read CSV, detect date/target, regularize
│   ├── profile.py               # statistics, ambiguities
│   ├── models.py                # registry + eligibility rules
│   ├── metrics.py               # MAE, RMSE, sMAPE, MASE
│   ├── backtest.py              # window planning + CV execution
│   ├── selection.py             # deterministic winner
│   ├── pipeline.py              # orchestrates a run
│   ├── diagnostics.py           # warnings, coverage, refusals
│   └── outputs.py               # csv/json writers, plot, text summary
├── schemas/                     # exported JSON Schema
├── tests/ (synthetic.py, test_*.py)
├── examples/ (CSVs + generator script)
├── pyproject.toml  README.md  LICENSE  plan.md
└── .github/workflows/ci.yml
```

---

## 12. Roadmap (one layer at a time)

**Phase 0 — Spikes and scaffold.** *Goal:* settle unknowns. Build a dummy plugin with root SKILL.md and with `skills/forecast/`; observe invocation name. Test `bin/` + `uv` wrapper. Install statsforecast, time cold start, check `fallback_model`. Check PyPI name. *Accept:* findings in `docs/decisions.md`; `claude plugin validate` passes.

**Phase 1 — Contracts and ingestion.** `schema.py`, `loading.py`, synthetic generators. *Accept:* date/target detection tested on ≥ 6 CSV shapes; regularization and fill-policy tests pass; schemas export.

**Phase 2 — Profiler and `forecast profile`.** Frequency, gaps, duplicates, outliers, intermittency, trend, seasonality, ambiguities. *Accept:* each profile field verified on known-truth synthetic series; `needs_input` output validates against schema.

**Phase 3 — Metrics and backtest planning (pure Python).** `metrics.py`, window planner, eligibility/refusal rules. *Accept:* metrics match hand-computed values; planner edge cases (short series, long horizon) behave as specified.

**Phase 4 — Model registry and CV execution.** Wrap StatsForecast, isolate failures, produce `backtest.csv`. *Accept:* all models run on a synthetic series; injected failure doesn't crash the run; columns match contract.

**Phase 5 — Selection and diagnostics.** `selection.py`, `diagnostics.py`. *Accept:* baseline wins on white noise; seasonal model wins on seasonal data; every warning code has a triggering test.

**Phase 6 — Final forecast and `forecast run`.** Refit, forecast, intervals, writers, exit codes. *Accept:* end-to-end on each example; horizon length exact; intervals bracket point forecast; `result.json` validates.

**Phase 7 — Chart and text summary.** *Accept:* PNG produced for every example; summary contains only values from `result.json`.

**Phase 8 — Skill and plugin.** SKILL.md, references, manifests, marketplace. *Accept:* works via `--plugin-dir` and via marketplace add from GitHub; `/forecast sales.csv` runs end to end; ambiguity flow asks then runs; Claude's answer matches `result.json` with no extra numbers.

**Phase 9 — Release polish.** README, CI, tune δ on synthetic benchmarks, tag `v0.1.0`. *Accept:* CI green; README states "LLM reasoning + deterministic statistics" with architecture diagram.

---

## 13. V1 completion checklist
- [ ] `forecast profile` and `forecast run` work with no Claude involved.
- [ ] Baseline always runs; a complex model must beat it by the margin.
- [ ] All warning codes tested.
- [ ] Refusal paths exist and are tested.
- [ ] Interval coverage measured and reported.
- [ ] Five demo datasets run end to end.
- [ ] Skill installs from GitHub; `/forecast sales.csv` works.
- [ ] CI green; README written.

## 14. Build order
Phase 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9. The skill comes last on purpose: the engine must be correct and standalone first.

## 15. Biggest technical/statistical risks
1. **Selection noise:** the rule and δ are only as good as the benchmarks; 3–5 windows stay noisy.
2. **Interval calibration:** native intervals may under-cover; we measure rather than assume.
3. **Claude Code distribution:** bare `/forecast` naming; Python dependency setup has no official mechanism.
4. **Install weight / cold start:** numba + statsforecast are heavy; first run is slow.
5. **Eligibility heuristics** (long seasonal periods, short series) need tuning.
6. **Unconfirmed StatsForecast details:** Theta signature, `fallback_model`, NaN handling.

## 16. Decisions needing approval
1. Invocation name: accept `/forecast:forecast` if bare `/forecast` isn't possible, or install a user-level skill via a setup step?
2. Primary metric: MASE instead of sMAPE?
3. Margin rule (non-baseline must beat baseline by δ, 3% start)?
4. Aggregate interval omitted in V1 unless estimable empirically?
5. CLI flags: include `--where`, `--agg`, `--fill`; defer `--group`, `--frequency`?
6. Models: include AutoTheta and HistoricAverage, subject to benchmark evidence?
7. Dependency mechanism: `uv` wrapper in `bin/` (vs SessionStart hook)?
8. Distribution name different from import name `forecast`?
9. pydantic v2 as a dependency?
10. Drop `report.md` in favour of Claude's narrative + CLI text summary?
11. License: MIT or Apache-2.0 (statsforecast is Apache-2.0)?
12. Default horizons (D→28, W→13, M→12, Q→4) and refusal rule?
13. Plugin and marketplace names (plugin `forecast`; marketplace name, given repo `forecastClaudeSkill`)?

## 17. V2+ (not built now)
Grouped/multi-series and hierarchical forecasting, intermittent-demand models, anomaly/changepoint detection, holidays, external regressors, reconciliation, Excel/Parquet/SQL input, interactive charts, batch forecasting, additional libraries, ML models, natural-language Q&A on results, automated business reports.

## Sources
- https://code.claude.com/docs/en/plugins
- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/plugin-marketplaces
- https://nixtlaverse.nixtla.io/statsforecast/src/core/core.html
- https://nixtlaverse.nixtla.io/statsforecast/docs/tutorials/conformalprediction.html
- https://pypi.org/project/statsforecast/
