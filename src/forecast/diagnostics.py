"""Statistical integrity checks: refusals and warnings that keep forecasts honest.

``WARNING_CODES`` is the complete catalogue of non-fatal codes the engine can emit, wherever
they originate (loader, profiler, planner, here). A test asserts every code is catalogued and
has a test that triggers it, so nothing can warn silently or be undocumented.
"""

from __future__ import annotations

import numpy as np

from forecast.schema import BacktestSummary, Notice, ProfileReport, RefusedError, Selection

WARNING_CODES: dict[str, str] = {
    # loading
    "TARGET_AUTO_SELECTED": "A target column was chosen automatically; alternatives existed.",
    "INVALID_VALUES": "Non-numeric target values were treated as missing.",
    "DATE_ROWS_DROPPED": "Rows with unparseable dates were dropped.",
    "DUPLICATE_ROWS_DROPPED": "Exact duplicate rows were dropped.",
    "UNBALANCED_PANEL": "Aggregated slices contribute unequal numbers of rows on different dates.",
    "OFF_CALENDAR_DROPPED": "Observations off the inferred calendar were dropped.",
    "EDGES_TRIMMED": "Leading/trailing periods with no value were trimmed.",
    "MISSING_FILLED": "Missing periods were filled by interpolation or zero.",
    # profiling
    "CONSTANT_SERIES": "Every observation has the same value.",
    "NEAR_CONSTANT": "At least 95% of observations share one non-zero value.",
    "INTERMITTENT": "Zero-heavy demand; only baseline models are run.",
    "NEGATIVE_VALUES": "The series contains negative values.",
    "OUTLIERS": "Potential outliers were flagged (never removed).",
    "SEASONALITY_UNTESTED": "Too little history to test for seasonality.",
    "NO_SEASONALITY": "No statistically significant seasonality at the tested periods.",
    "MULTIPLE_SEASONALITY": "More than one seasonal pattern; only the primary is modelled.",
    "SHORT_HISTORY": "Few observations (or few seasonal cycles) for reliable estimation.",
    # planning
    "HORIZON_DEFAULT_REDUCED": "The default horizon was reduced to what history can back-test.",
    "BACKTEST_HORIZON_SHORTENED": "Models were scored on a shorter horizon than the one forecast.",
    "HORIZON_LONG": "The horizon is a large share of the available history.",
    "FEW_BACKTEST_WINDOWS": "Selection rests on fewer than the maximum number of windows.",
    # backtest
    "MODEL_FAILED": "A model failed during the backtest and was excluded.",
    "MODEL_ADJUSTED": "The selected model was run with an adjusted configuration.",
    "BASELINE_WON": "A baseline model was selected over the complex models.",
    "POOR_BACKTEST": "The selected model's error exceeds a one-step in-sample seasonal-naive error.",
    "UNSTABLE_ACROSS_WINDOWS": "The selected model's accuracy varies a lot between backtest windows.",
    "RECENT_DEGRADATION": "The latest backtest window was much worse than earlier ones.",
    "LOW_COVERAGE": "The selected model's 80% interval contained far fewer than 80% of actuals.",
    "WIDE_INTERVALS": "The 80% interval is very wide compared with the spread of the history.",
    # forecasting
    "WINNER_REFIT_FAILED": "The selected model could not be refit on the full history; the next best was used.",
    "INTERVALS_CALIBRATED": "Backtest coverage was far from nominal, so the intervals were rescaled.",
    "FORECAST_CLIPPED": "Negative forecast values were raised to zero because the history is non-negative.",
    # output
    "PLOT_FAILED": "The chart could not be drawn; all other result files were written.",
}

SHORT_HISTORY_OBS = 50
SHORT_HISTORY_CYCLES = 3
POOR_MASE = 1.0
LOW_COVERAGE_80 = 0.65  # nominal 0.80; allows for sampling noise over a few correlated windows
UNSTABLE_CV = 0.5  # std / mean of the winner's per-window MAE
UNSTABLE_WIN_FRACTION = (
    0.5  # a complex winner must beat the baseline in at least this share of windows
)
DEGRADATION_RATIO = 1.5  # last window's MAE vs the mean of the earlier ones
WIDE_IQR_RATIO = 3.0  # mean 80% interval width vs the inter-quartile range of the history


def check_forecastable(profile: ProfileReport) -> None:
    """Raise ``RefusedError`` when the data cannot support any meaningful forecast."""
    if profile.constant:
        raise RefusedError(
            "CONSTANT_SERIES",
            f"Every observation equals {profile.stats.min:g}. A statistical forecast would only "
            "repeat that value and its uncertainty cannot be estimated from the data.",
            value=profile.stats.min,
        )


def series_notices(profile: ProfileReport) -> list[Notice]:
    """Warnings decidable from the profile alone."""
    n, m = profile.stats.n, profile.seasonality.season_length
    if n < SHORT_HISTORY_OBS or (m > 1 and n < SHORT_HISTORY_CYCLES * m):
        return [
            Notice(
                code="SHORT_HISTORY",
                severity="warn",
                message=f"Only {n} observations"
                + (f" ({n / m:.1f} seasonal cycles)" if m > 1 else "")
                + "; estimates from so little history are fragile.",
                details={"n_obs": n, "season_length": m},
            )
        ]
    return []


def backtest_notices(
    summary: BacktestSummary, selection: Selection, profile: ProfileReport
) -> list[Notice]:
    """Warnings that depend on how the models actually performed."""
    out: list[Notice] = []
    by_name = {m.name: m for m in summary.models}
    for m in summary.models:
        if m.status == "failed":
            out.append(
                Notice(
                    code="MODEL_FAILED",
                    severity="warn",
                    message=f"{m.name} failed during the backtest and was excluded: {m.reason}",
                    details={"model": m.name},
                )
            )
    winner = by_name[selection.winner]
    metrics = winner.metrics
    if winner.reason:
        out.append(
            Notice(
                code="MODEL_ADJUSTED",
                severity="info",
                message=f"{winner.name} was run with an adjusted configuration: {winner.reason}.",
                details={"model": winner.name},
            )
        )

    complex_ran = any(m.status == "ok" and m.kind == "complex" for m in summary.models)
    if selection.winner_kind == "baseline" and complex_ran:
        out.append(
            Notice(
                code="BASELINE_WON",
                severity="info",
                message=f"No complex model was clearly better than the {winner.name} baseline "
                f"({selection.reason.replace('_', ' ')}); the forecast is the simple baseline's.",
                details={"reason": selection.reason, "baseline": winner.name},
            )
        )

    if selection.metric == "mase" and metrics.mase >= POOR_MASE:
        out.append(
            Notice(
                code="POOR_BACKTEST",
                severity="warn",
                message=f"Typical backtest error (MASE {metrics.mase:.2f}) is larger than the "
                "one-step in-sample error of a seasonal-naive forecast. Expect forecasts to be "
                "imprecise, especially at long horizons.",
                details={"mase": round(metrics.mase, 4)},
            )
        )

    windows = np.asarray(metrics.window_mae, dtype=float)
    unstable = []
    if len(windows) >= 2 and windows.mean() > 0 and windows.std() / windows.mean() >= UNSTABLE_CV:
        unstable.append(f"window errors vary by {windows.std() / windows.mean():.0%} (std/mean)")
    base = by_name.get(selection.best_baseline) if selection.best_baseline else None
    if selection.winner_kind == "complex" and base is not None and base.metrics is not None:
        wins = int(np.sum(windows < np.asarray(base.metrics.window_mae)))
        if wins < UNSTABLE_WIN_FRACTION * len(windows):
            unstable.append(f"it beat the baseline in only {wins} of {len(windows)} windows")
    if unstable:
        out.append(
            Notice(
                code="UNSTABLE_ACROSS_WINDOWS",
                severity="warn",
                message=f"{winner.name}'s accuracy is unstable across backtest windows: "
                + "; ".join(unstable)
                + ".",
                details={"window_mae": [round(float(w), 6) for w in windows]},
            )
        )

    if (
        len(windows) >= 3
        and windows[:-1].mean() > 0
        and windows[-1] >= DEGRADATION_RATIO * windows[:-1].mean()
    ):
        out.append(
            Notice(
                code="RECENT_DEGRADATION",
                severity="warn",
                message="The most recent backtest window was much less accurate than earlier ones "
                f"({windows[-1] / windows[:-1].mean():.1f}x), which can indicate a recent change in behaviour. "
                "Older history may no longer describe the series.",
                details={"last_over_earlier": round(float(windows[-1] / windows[:-1].mean()), 3)},
            )
        )

    if metrics.coverage_80 < LOW_COVERAGE_80:
        out.append(
            Notice(
                code="LOW_COVERAGE",
                severity="warn",
                message=f"The nominal 80% prediction interval of {winner.name} contained only "
                f"{metrics.coverage_80:.0%} of backtest actuals; its intervals understate the uncertainty.",
                details={"coverage_80": round(metrics.coverage_80, 4), "nominal": 0.8},
            )
        )

    iqr = profile.stats.q75 - profile.stats.q25
    if iqr > 0 and metrics.mean_width_80 >= WIDE_IQR_RATIO * iqr:
        out.append(
            Notice(
                code="WIDE_INTERVALS",
                severity="warn",
                message=f"The 80% interval is {metrics.mean_width_80 / iqr:.1f}x the inter-quartile range of "
                "the history, so the forecast says little beyond 'somewhere in the usual range'.",
                details={"width_over_iqr": round(metrics.mean_width_80 / iqr, 3)},
            )
        )
    return out
