# How the engine selects a model

You do not choose the model; this is what you need in order to explain the engine's choice.

## Backtesting (rolling origin)

The engine tests each model the way it will be used: train on the past, forecast the next
`horizon` periods, score against what actually happened, then repeat with a longer past.

```
TRAIN ───────────── TEST
TRAIN ───────────────── TEST
TRAIN ───────────────────── TEST
```

- 3 to 5 windows, each as long as the forecast horizon, packed against the end of the series, so
  the most recent behaviour is always tested.
- Training windows grow (they never shrink or skip), and every forecast is strictly out of sample:
  nothing is judged on data the model has seen.
- If history is too short to test the full horizon, the test horizon is shortened (with a
  warning, `BACKTEST_HORIZON_SHORTENED`) down to a floor, and below that the run refuses
  (`HORIZON_TOO_LONG`).
- Selection is never based on training-set fit, on how a chart looks, or on anyone's opinion.

## The score: MASE

Mean Absolute Scaled Error: the model's average absolute error across all test points, divided by
the average error of a seasonal-naive forecast on the training data (repeat last season; or the
last value if no season was found).

Why not sMAPE or MAPE: they blow up or mislead near zero, and fail outright on zero-heavy demand.
MASE is scale-free, defined with zeros, and easy to read against a baseline: below 1 beats the
yardstick, above 1 does not. MAE, RMSE and sMAPE are reported alongside for context.

## The rule

1. Score every model that completed the backtest.
2. Find the best **baseline** (Naive, SeasonalNaive, HistoricAverage) and the best **complex**
   model (AutoETS, AutoTheta, AutoARIMA).
3. A complex model wins only if its score is **at least 5% better** than the best baseline's.
   Otherwise the baseline wins.
4. Ties go to the simpler model. Listing order never matters.

The 5% margin exists because three to five short windows are noisy: on a pure random walk (nothing
to learn) a complex model beats the baseline by chance 30% of the time at a 3% margin and 15% at
5%. Real structure (trend, seasonality) clears the margin by 20% or far more.

The engine's `selection.reason` is one of:

| Reason | Say |
|---|---|
| `beat_baseline_by_margin` | "<model> beat the best simple baseline (<baseline>) by <improvement>, more than the 5% required." |
| `baseline_within_margin` | "A complex model was slightly better but not by enough to justify the added complexity." |
| `baseline_best` | "No complex model beat the baseline." |
| `only_baselines_ran` | "Only baselines were run (for example because most values are zero)." |
| `no_baseline_ran` | "Every baseline failed, so the best remaining model was used." |

## The models and why each exists

| Model | Kind | Why it is there |
|---|---|---|
| Naive | baseline | "Tomorrow = today". The minimum bar; optimal for a random walk. |
| SeasonalNaive | baseline | "Same as one season ago". The bar for seasonal data; only run when a period was found. |
| HistoricAverage | baseline | The overall mean: the right answer for noise around a constant. |
| AutoETS | complex | Exponential smoothing with automatic trend/season choice; strong general default. |
| AutoTheta | complex | Robust, cheap, good on short series. |
| AutoARIMA | complex | Captures autocorrelation structure that ETS cannot. |

Complex models are skipped when most values are zero (intermittent demand), and run without
seasonality when the period is too long for them (`MODEL_ADJUSTED`).

## Intervals

Models give their own intervals. The engine measures how often they actually contained the truth
in the backtest. If the 80% interval covered under 60% of test points, the intervals are widened
(never narrowed) so backtest coverage matches (`INTERVALS_CALIBRATED`). That measurement is on
the same points used to fit the correction, so real coverage will be somewhat lower.

## Limits to be honest about

- Three to five windows is limited evidence. Say so when `FEW_BACKTEST_WINDOWS` appears.
- The backtest says how the model *would have done*. It cannot see regime changes that have not
  happened yet.
- One seasonal period is modelled (the shortest significant one). Holidays, promotions and
  external drivers are not modelled in V1.
- A forecast is a distribution, not a promise. Always give the interval.
