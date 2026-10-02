# Interpreting and explaining a forecast

## Three kinds of statement - never mix them

| Kind | Source | Phrase it as |
|---|---|---|
| **Observed fact** | `input`, `profile` in `result.json` | "The data show...", "Over the 731 observations..." |
| **Forecast** | `forecast`, `intervals`, `selection` | "The model forecasts...", "The selected model expects..." |
| **Interpretation** | You | "One possible reading, which the data cannot confirm, is..." |

Interpretations are optional. Offer one only when it helps, say it is a hypothesis, and say what
domain knowledge would confirm or reject it. Correlation, seasonality or a trend never tell you
*why*; do not write "because", "due to", "driven by" or "caused by" about the data.

## Numbers

- Quote engine numbers exactly as printed. No rounding of your own, no `k`/`M` abbreviations, no
  arithmetic (do not add, subtract, convert units, or work out percentages the engine did not give).
- The engine gives you: the sum of forecasts, the previous period's sum, the change between them,
  the mean per period, first- and last-period 80%/95% intervals, backtest scores (MASE, MAE,
  sMAPE), coverage, and counts. If you need a number that is not there, say it is not available.
- Do not add a currency or unit the user did not give.

## Reading the scores

- **MASE** compares the model's backtest error with the error of simply repeating the pattern from
  one season ago (or the last value, if there is no season) on the training data. Below 1: better
  than that yardstick; above 1: worse. Multi-step forecasts are naturally harder than one-step
  ones, so values above 1 are normal at long horizons and are *not* a warning sign by themselves
  (a good forecast of a steadily growing series can score 1.8). What matters is the improvement
  over simply repeating the last value (`selection.improvement_over_naive`).
- **sMAPE** is a percentage error. It is unstable near zero, which is why selection does not use it.
- **Coverage** of the 80% interval should be near 80%. Far below means the model was overconfident.

## Explaining uncertainty

"The 80% interval for <date> is <lo> to <hi>": the model expects roughly four in five outcomes to
fall inside, if the backtest is representative. Intervals usually widen with the horizon, but not always (some models give flat
intervals). Use `forecast.interval_width_growth` (width at the last period over width at the first):
say the interval widens only if it is clearly above 1; never work it out yourself. Never present the point forecast alone.

## Warnings: what each one means and how to say it

Mention every `warn` warning. Mention `info` notices only when they matter to the question.

### Data quality (loading)

| Code | Plain-language version |
|---|---|
| `TARGET_AUTO_SELECTED` | (info) "I forecast <column>; the other numeric columns were <alternatives>." Offer to switch. |
| `INVALID_VALUES` | "<n> values in the target were not numbers and were treated as missing." |
| `DATE_ROWS_DROPPED` | "<n> rows had dates that could not be read and were left out." |
| `DUPLICATE_ROWS_DROPPED` | (info) "Exact duplicate rows were removed." |
| `UNBALANCED_PANEL` | "The combined series dips on dates where some stores/products have no row, so the total may be understated there." |
| `OFF_CALENDAR_DROPPED` | "A few observations did not fit the regular calendar and were dropped." |
| `EDGES_TRIMMED` | (info) "Empty periods at the start or end of the data were removed." |
| `MISSING_FILLED` | "<n> missing periods were filled in (by interpolation or zero) so the series is complete; the longest gap was <k>." Filled points are shown hollow on the chart. |

### What the profile found

| Code | Plain-language version |
|---|---|
| `CONSTANT_SERIES` | Every value is identical; there is nothing to forecast. |
| `NEAR_CONSTANT` | Almost every value is the same, so forecasts will be nearly flat. |
| `INTERMITTENT` | "Most days have zero. Standard models handle this poorly, so only simple baselines were used, and the intervals deserve extra caution." Intermittent-demand models are not in V1. |
| `NEGATIVE_VALUES` | (info) The series goes below zero, so forecasts are not floored at zero. |
| `OUTLIERS` | "<n> unusually large or small points were flagged. They were kept in the data; if they are errors or one-off events, the forecast could change without them." Do not claim they are errors. |
| `SEASONALITY_UNTESTED` | (info) There was too little history to test for a repeating pattern. |
| `NO_SEASONALITY` | (info) No statistically significant repeating pattern was found at the standard periods. |
| `MULTIPLE_SEASONALITY` | "More than one repeating pattern is present (e.g. weekly and yearly); V1 models only the shortest, so the longer pattern is not captured." |
| `SHORT_HISTORY` | "There is little history, so estimates (and the model choice) are fragile." |

### The backtest and the horizon

| Code | Plain-language version |
|---|---|
| `HORIZON_DEFAULT_REDUCED` | (info) "No horizon was given; the default was shortened to what the history can test." |
| `BACKTEST_HORIZON_SHORTENED` | "There is not enough history to test <horizon>-step forecasts, so models were scored on <backtest_horizon>-step ones. Accuracy at the full horizon is probably worse than measured." |
| `HORIZON_LONG` | "The horizon is a large share of the history; long-range forecasts are unreliable." |
| `FEW_BACKTEST_WINDOWS` | (info) "Selection rests on only <n> backtest windows, so the ranking is noisy." Say this when explaining the choice. |
| `MODEL_FAILED` | "<model> failed during testing and was excluded: <reason>. The others were unaffected." |
| `MODEL_ADJUSTED` | (info) "<model> ran with a reduced setting (<reason>)." |
| `BASELINE_WON` | (info) "No complex model clearly beat the simple baseline. That is informative: the data do not reward sophistication." |
| `POOR_BACKTEST` | "In testing, the selected model was barely better than (or no better than) simply repeating the last observation, so it adds little skill. Treat the forecast as rough." Use the percentage in the message; do not recompute it. |
| `UNSTABLE_ACROSS_WINDOWS` | "The model's accuracy swung a lot between test periods (or it rarely beat the baseline period by period), so how well it will do next is uncertain." |
| `RECENT_DEGRADATION` | "The most recent test period was much worse than earlier ones. That can mean the series' behaviour recently changed, which the model has not learned. Whether it did, and why, is for the user to judge." |
| `LOW_COVERAGE` | "The model's 80% intervals contained far fewer than 80% of the actual values in testing: they understate the uncertainty." |
| `WIDE_INTERVALS` | "The 80% interval is many times the history's usual spread, so the forecast says little beyond 'somewhere in the usual range'." |

### The forecast itself

| Code | Plain-language version |
|---|---|
| `WINNER_REFIT_FAILED` | "The selected model could not be refit on the full history, so the next best in the testing ranking produced the forecast." Say which model was used (`forecast.model`) and that the selection named a different one. |
| `INTERVALS_CALIBRATED` | "The model's own intervals were too narrow in testing (they contained <native_coverage_80> of actuals), so they were widened by <factor>. After widening, coverage on the test data matched, but on genuinely new data it will be somewhat lower." |
| `FORECAST_CLIPPED` | (info) "Negative forecasts or bounds were raised to zero because the history never goes negative." |
| `PLOT_FAILED` | "The chart could not be drawn; the forecast and all other files were written." |
| `DASHBOARD_FAILED` | "The interactive dashboard could not be built; the forecast, chart and all other files were written." Say there is no dashboard to open; do not try to build one yourself. |

## Refusals (exit code 4)

Explain in one or two sentences and offer a way forward. Do not rerun with different settings
unless the user agrees.

| Code | Meaning and what to offer |
|---|---|
| `FILE_UNREADABLE` | File missing, empty or not a table. Check the path/format. |
| `BAD_ARGUMENT` | A flag named a column that does not exist, or a bad value. Show the available columns (in the message details) and ask. |
| `NO_DATE_COLUMN` | No column looks like dates. Ask which column is the time axis, or whether the file has one. |
| `NO_TARGET_COLUMN` | No numeric column to forecast. |
| `DATE_PARSE_FAILED` | Most values in the date column are not dates. |
| `INSUFFICIENT_DATA` | Too few observations to test any forecast fairly (the message gives the minimum). More history is the only fix. |
| `IRREGULAR_SAMPLING` | Observations are not evenly spaced (e.g. sporadic events). Forecasting needs a regular series; suggest aggregating to day/week/month first. |
| `MISSING_DATA_HIGH` | More than 10% of periods are empty; filling that much would be inventing data. Offer `--fill zero` only if zero is the right meaning for a missing period, which only the user can say. |
| `WHERE_NO_MATCH` | The `--where` filter matched no rows; check the value. |
| `HORIZON_TOO_LONG` | The history cannot validate that horizon; the message gives the maximum that can. Offer the shorter horizon. |
| `CONSTANT_SERIES` | Every value is identical, so there is nothing to forecast. |
| `NO_VALID_MODEL` | Every model failed in testing; report the failures from the details. |

## Things not to say

- "The model predicts..." as if certain. Use "forecasts" and give the interval.
- "AI predicts". The statistics are deterministic; say the engine selected the model by backtest.
- Anything about causes, intent, seasons' reasons, customer behaviour, or what "will" happen.
- That a more complex model "should" be better. Evidence decides; sometimes a baseline wins.
- Recommendations to act on the forecast (inventory, hiring, spend). Offer to discuss implications
  only if asked, and keep to the numbers.
