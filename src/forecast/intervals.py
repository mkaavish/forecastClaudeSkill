"""Prediction-interval calibration from backtest errors.

Phase 4 measured native intervals on data with known behaviour: AutoETS/AutoARIMA cover about
80% of actuals at the nominal 80% level, but SeasonalNaive covered 47% and HistoricAverage 0%
(Naive 97%). A baseline can win selection, so intervals are checked against the backtest and
rescaled when they miss badly.

The method is split-conformal in spirit: for every backtest point, divide the absolute error
by the model's own half-width on the side the error fell on; the (n+1)-adjusted quantile of
those ratios is the factor that would have given exactly nominal coverage. Each side of the
final intervals is multiplied by it, so the model's own shape (growth with the horizon,
asymmetry) is kept and only its level is corrected.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from forecast.schema import IntervalInfo, Notice

LEVELS = (80, 95)
# Widen-only, and only for gross under-coverage. Measured out-of-sample (10 seeds x 14 steps):
#   linear trend, baselines only: native 80% coverage 0.18 -> 0.89 when widened (the case this is for)
#   random walk: recalibrating at 0.70/0.90 moved a fine 0.78 to 0.71 (a few correlated windows
#   make coverage estimates noisy), at 0.60/0.95 still 0.71; widen-only below 0.60 left it at 0.78.
# Narrowing is never done: overstating precision is the costlier error.
CALIBRATE_BELOW = 0.60  # native backtest coverage of the nominal 80% interval
MIN_POINTS = 30
MAX_FACTOR = 8.0  # needing more than this means the model's intervals are unusable as a shape


def _ratios(frame: pd.DataFrame, level: int) -> np.ndarray:
    err = (frame["y"] - frame["yhat"]).to_numpy()
    upper = (frame[f"hi_{level}"] - frame["yhat"]).to_numpy()
    lower = (frame["yhat"] - frame[f"lo_{level}"]).to_numpy()
    side = np.where(err >= 0, upper, lower)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(side > 0, np.abs(err) / side, np.where(err == 0, 0.0, np.inf))
    return ratio


def conformal_factor(frame: pd.DataFrame, level: int) -> float | None:
    """Width multiplier achieving ``level``% coverage on ``frame``; None if it is unusable.

    The factor is never below 1: intervals are only ever widened.
    """
    ratios = np.sort(_ratios(frame, level))
    n = len(ratios)
    if n == 0:
        return None
    k = min(n, math.ceil((n + 1) * level / 100))
    factor = float(ratios[k - 1])
    if not math.isfinite(factor) or factor > MAX_FACTOR:
        return None
    return max(factor, 1.0)


def _scaled(
    frame: pd.DataFrame, level: int, factor: float, point: str
) -> tuple[pd.Series, pd.Series]:
    """Multiply each side's distance from the point forecast by ``factor``."""
    lo = frame[point] - factor * (frame[point] - frame[f"lo_{level}"])
    hi = frame[point] + factor * (frame[f"hi_{level}"] - frame[point])
    return lo, hi


def _coverage(frame: pd.DataFrame, lo, hi) -> float:
    return float(np.mean((frame["y"] >= lo) & (frame["y"] <= hi)))


def calibrate(
    backtest_rows: pd.DataFrame, forecast: pd.DataFrame, model: str
) -> tuple[pd.DataFrame, IntervalInfo, list[Notice]]:
    """Return (forecast with final intervals, how they were made, notices).

    ``backtest_rows`` holds the backtest frame for the model that produced ``forecast``.
    """
    n = len(backtest_rows)
    native80 = _coverage(backtest_rows, backtest_rows["lo_80"], backtest_rows["hi_80"])
    native95 = _coverage(backtest_rows, backtest_rows["lo_95"], backtest_rows["hi_95"])
    info = IntervalInfo(method="native", backtest_points=n, native_coverage_80=native80,
                        native_coverage_95=native95, factor_80=None, factor_95=None,
                        calibrated_coverage_80=None, calibrated_coverage_95=None)  # fmt: skip
    if native80 >= CALIBRATE_BELOW:
        return forecast, info, []
    if n < MIN_POINTS:
        info.note = f"Native 80% coverage was {native80:.0%} but only {n} backtest points exist (need {MIN_POINTS}) to recalibrate."
        return forecast, info, []
    f80, f95 = conformal_factor(backtest_rows, 80), conformal_factor(backtest_rows, 95)
    if f80 is None or f95 is None:
        info.note = f"Native 80% coverage was {native80:.0%} and the intervals could not be rescaled (degenerate widths)."
        return forecast, info, []

    out = forecast.copy()
    for level, factor in ((80, f80), (95, f95)):
        out[f"lo_{level}"], out[f"hi_{level}"] = _scaled(forecast, level, factor, "forecast")
    # keep the nested ordering lo95 <= lo80 <= yhat <= hi80 <= hi95
    out["lo_95"] = np.minimum(out["lo_95"], out["lo_80"])
    out["hi_95"] = np.maximum(out["hi_95"], out["hi_80"])
    lo80, hi80 = _scaled(backtest_rows, 80, f80, "yhat")
    lo95, hi95 = _scaled(backtest_rows, 95, f95, "yhat")
    info = info.model_copy(update={
        "method": "calibrated", "factor_80": f80, "factor_95": f95,
        "calibrated_coverage_80": _coverage(backtest_rows, lo80, hi80),
        "calibrated_coverage_95": _coverage(backtest_rows, lo95, hi95),
        "note": "Rescaled so the backtest coverage matches the nominal level (fitted on the same points, so "
                "out-of-sample coverage will be somewhat lower).",
    })  # fmt: skip
    notice = Notice(code="INTERVALS_CALIBRATED", severity="info",
                    message=f"{model}'s own 80% intervals were too narrow: they contained {native80:.0%} of "
                            f"backtest actuals. They were rescaled by {f80:.2f}x (80%) and {f95:.2f}x (95%).",
                    details={"native_coverage_80": round(native80, 4), "factor_80": round(f80, 4),
                             "factor_95": round(f95, 4)})  # fmt: skip
    return out, info, [notice]
