# /forecast

**Statistically backtested time-series forecasting, directly from Claude Code.**

`/forecast` is an open-source Claude Code skill that turns time-series datasets into forecasts using deterministic statistical models, rolling backtests, automatic model selection, and plain-English analysis.

<a href="https://forecast-skill.vercel.app">
  <img src="https://img.shields.io/badge/Website%20%26%20Documentation-Visit-000000?style=for-the-badge" alt="Website & Documentation">
</a>

```bash
/forecast sales.csv
```

> **Claude understands the problem. Python does the math.**

---

## What it does

Give `/forecast` a time-series dataset:

```csv
date,sales
2026-01-01,18422
2026-01-02,19201
2026-01-03,18832
...
```

Then run:

```bash
/forecast sales.csv
```

`/forecast` handles the forecasting workflow:

```text
Dataset
   ↓
Profile & validate
   ↓
Detect frequency / trend / seasonality
   ↓
Prepare time series
   ↓
Run candidate models
   ↓
Rolling backtests
   ↓
Compare forecast error
   ↓
Select best model
   ↓
Generate forecast + intervals
   ↓
Claude explains the results
```

The goal isn't to pick the most sophisticated model.

The goal is to pick the model that performs best on historical data.

---

## Why `/forecast`?

LLMs are useful for understanding data and explaining results.

They are not forecasting engines.

`/forecast` separates those responsibilities.

### Claude

Claude handles:

- understanding the dataset
- interpreting user intent
- identifying potential forecasting problems
- resolving ambiguous columns
- orchestrating the analysis
- interpreting model results
- explaining forecasts in plain English

### Python

Python handles:

- data validation
- statistical calculations
- frequency inference
- time-series preprocessing
- backtesting
- model fitting
- error metrics
- model selection
- prediction intervals
- forecast generation
- visualization

This keeps the statistical pipeline deterministic while still taking advantage of Claude's reasoning capabilities.

---

## Example

```bash
/forecast revenue.csv --horizon 30
```

Example output:

```text
FORECAST ANALYSIS

Target
Revenue

Frequency
Daily

Forecast horizon
30 days

Historical observations
1,004

Pattern
Positive trend with strong weekly seasonality

Selected model
AutoETS

Backtesting sMAPE
6.2%

Why this model?
AutoETS achieved the lowest rolling cross-validation
error among the tested models.

Forecast
$782,000 expected revenue over the next 30 days

Prediction interval
$711,000 – $851,000

Risk
Forecast uncertainty increases toward the end of
the forecast horizon.
```

---

## Model selection

`/forecast` doesn't ask Claude which forecasting model "looks best."

Candidate models are evaluated against historical data using rolling backtests.

Initial models are planned to include:

- **Naive**
- **Seasonal Naive**
- **AutoETS**
- **AutoARIMA**

A simple baseline is always included.

If a baseline beats a more sophisticated model, **the baseline wins**.

Model complexity does not equal forecast accuracy.

---

## Backtesting

Forecasting models should be evaluated on their ability to predict observations they haven't seen.

`/forecast` uses rolling-origin time-series cross-validation.

```text
Time ───────────────────────────────────────────▶

Fold 1
[──────── TRAIN ────────][ TEST ]

Fold 2
[─────────── TRAIN ─────────][ TEST ]

Fold 3
[────────────── TRAIN ──────────][ TEST ]
```

Candidate models are compared using forecast-error metrics such as:

- **MAE** — Mean Absolute Error
- **RMSE** — Root Mean Squared Error
- **sMAPE** — Symmetric Mean Absolute Percentage Error

Model selection is deterministic and based on backtesting performance rather than LLM judgment.

---

## Data validation

Before forecasting, `/forecast` inspects the dataset for issues that could affect forecast quality.

This includes checking for:

- missing observations
- missing timestamps
- duplicate timestamps
- irregular frequencies
- invalid values
- insufficient history
- constant series
- potential outliers
- possible seasonality
- trend characteristics

If the data isn't suitable for reliable forecasting, `/forecast` can say so instead of forcing a prediction.

---

## Ambiguous datasets

Real datasets aren't always:

```text
date | sales
```

For example:

```text
date | store | product | units_sold | inventory | price
```

could represent several different forecasting problems.

Claude may identify possibilities such as:

```text
Total units sold
Units sold by store
Units sold by product
Store × product demand
```

When there is no clear interpretation, `/forecast` asks instead of silently choosing one.

---

## Usage

Basic forecast:

```bash
/forecast sales.csv
```

Specify a forecast horizon:

```bash
/forecast sales.csv --horizon 30
```

Specify a target:

```bash
/forecast revenue.csv --target revenue
```

Grouped forecasting is planned for a later release:

```bash
/forecast demand.csv --target units_sold --group product
```

The interface is intentionally designed around intelligent defaults rather than dozens of required options.

---

## Outputs

A `/forecast` run is designed to produce artifacts such as:

```text
forecast-results/
├── forecast.csv
├── forecast.png
├── metrics.json
├── profile.json
└── report.md
```

### `forecast.csv`

Machine-readable forecast results.

```text
timestamp
forecast
lower_bound
upper_bound
model
```

### `metrics.json`

Backtesting performance and model comparison results.

### `profile.json`

Structured information about the detected time series and data-quality checks.

### `forecast.png`

Historical observations, forecast values, and prediction intervals.

### `report.md`

Human-readable forecast analysis.

Exact output schemas may change while `/forecast` is under development.

---

## Architecture

```text
                  /forecast sales.csv
                          │
                          ▼
                 ┌─────────────────┐
                 │     Claude      │
                 │  Analyst Layer  │
                 └────────┬────────┘
                          │
                          ▼
                  Dataset Profiler
                          │
                          ▼
                     Validation
                          │
                          ▼
                 Time-Series Engine
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
            Naive      AutoETS    AutoARIMA
              │           │           │
              └───────────┼───────────┘
                          ▼
                     Backtesting
                          │
                          ▼
                   Model Selection
                          │
                          ▼
                       Forecast
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
         forecast.csv   chart    metrics.json
                          │
                          ▼
                        Claude
                          │
                          ▼
                  Plain-English Report
```

---

## Standalone forecasting engine

The statistical engine is being designed to work independently of Claude Code.

The eventual CLI will resemble:

```bash
forecast sales.csv --horizon 30
```

or:

```bash
python -m forecast sales.csv --horizon 30
```

Claude Code is therefore an intelligent interface to the forecasting engine — not the engine performing the calculations.

---

## Tech stack

### Agent layer

- Claude Code
- Claude Code Skills

### Data & forecasting

- Python
- pandas
- StatsForecast

### Statistics

- NumPy
- SciPy and other statistical utilities where appropriate

### Visualization

- Matplotlib

### Testing

- pytest

Dependencies may change as development progresses.

---

## Statistical integrity

`/forecast` is designed around a few core principles.

### Backtest everything

Models should demonstrate predictive performance against historical unseen data.

### Always compare against a baseline

A more complicated model isn't automatically a better model.

### Don't hide uncertainty

Forecasts should include prediction intervals where statistically appropriate.

### Don't force forecasts

Sometimes the correct answer is that there isn't enough reliable data.

### Don't confuse correlation with causation

Claude may describe patterns in the data but should not invent causal explanations.

### Don't let the LLM do the math

Statistical computation belongs in deterministic code.

---

## Status

> **Early development**

`/forecast` is currently under active development.

The API, command options, output schemas, models, and installation process may change before the first stable release.

### V1

- [ ] Claude Code `/forecast` skill
- [ ] CSV ingestion
- [ ] automatic date-column detection
- [ ] automatic target detection
- [ ] frequency inference
- [ ] data-quality validation
- [ ] Naive baseline
- [ ] Seasonal Naive baseline
- [ ] AutoETS
- [ ] AutoARIMA
- [ ] rolling-origin backtesting
- [ ] MAE / RMSE / sMAPE evaluation
- [ ] deterministic model selection
- [ ] prediction intervals
- [ ] forecast visualization
- [ ] `forecast.csv`
- [ ] `metrics.json`
- [ ] plain-English analysis
- [ ] standalone Python CLI
- [ ] automated tests
- [ ] synthetic example datasets
- [ ] Claude Code installation documentation

---

## Roadmap

Future versions may explore:

- grouped and multiple time series
- hierarchical forecasting
- intermittent-demand forecasting
- changepoint detection
- anomaly detection
- holiday and event effects
- external regressors
- forecast reconciliation
- Excel and Parquet support
- SQL and database sources
- batch forecasting
- additional statistical models
- ML forecasting models
- interactive visualizations
- natural-language questions about forecast results

The focus for V1 is intentionally smaller:

> **Make one time-series forecast correctly and explain it well.**

---

## Example datasets

The repository will include synthetic datasets for testing and demonstration:

```text
examples/
├── retail_sales.csv
├── saas_revenue.csv
├── website_traffic.csv
└── inventory_demand.csv
```

These datasets will demonstrate patterns including trend, seasonality, missing observations, noise, and intermittent demand.

---

## Contributing

`/forecast` is early in development and contributions are welcome.

Issues, bug reports, forecasting edge cases, model suggestions, documentation improvements, and pull requests are all appreciated.

When proposing a new forecasting model, the question shouldn't simply be:

> "Is this model more advanced?"

It should be:

> **"Does this improve forecasting performance or support a use case the existing models cannot handle?"**

---

## Documentation

<a href="https://forecast-skill.vercel.app">
  <img src="https://img.shields.io/badge/Website%20%26%20Documentation-Visit-000000?style=for-the-badge" alt="Website & Documentation">
</a>

---

## License

MIT

---

<p align="center">
  <strong>/forecast</strong>
  <br>
  <em>Claude understands the problem. Python does the math.</em>
</p>
