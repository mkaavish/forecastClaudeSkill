"""Forecast accuracy metrics: pure functions over arrays, no model or I/O dependencies.

``mase`` is the model-selection metric. It is scale-free, defined when the series contains
zeros (unlike sMAPE/MAPE), and reads directly against the baseline: below 1 means the model
beats the in-sample seasonal-naive forecast.
"""

from __future__ import annotations

import numpy as np


def _pair(actual, forecast) -> tuple[np.ndarray, np.ndarray]:
    a = np.asarray(actual, dtype=float)
    f = np.asarray(forecast, dtype=float)
    if a.shape != f.shape or a.ndim != 1:
        raise ValueError(
            f"actual and forecast must be 1-D and equal length, got {a.shape} and {f.shape}"
        )
    if a.size == 0:
        raise ValueError("cannot score an empty forecast")
    return a, f


def mae(actual, forecast) -> float:
    a, f = _pair(actual, forecast)
    return float(np.mean(np.abs(a - f)))


def rmse(actual, forecast) -> float:
    a, f = _pair(actual, forecast)
    return float(np.sqrt(np.mean((a - f) ** 2)))


def smape(actual, forecast) -> float:
    """Symmetric MAPE in percent (0-200 scale): 200 * mean(|e| / (|a| + |f|)).

    A period where actual and forecast are both zero counts as a perfect forecast (0).
    Unstable for series near zero, which is why it is reported but not used to select.
    """
    a, f = _pair(actual, forecast)
    denom = np.abs(a) + np.abs(f)
    terms = np.divide(np.abs(a - f), denom, out=np.zeros_like(denom), where=denom > 0)
    return float(200.0 * np.mean(terms))


def mase_scale(insample, season_length: int = 1) -> float | None:
    """Mean absolute seasonal-naive error on the training data (the MASE denominator).

    Returns None when it is zero (a flat history), where MASE is undefined.
    """
    y = np.asarray(insample, dtype=float)
    m = max(int(season_length), 1)
    if y.size <= m:
        raise ValueError(f"need more than season_length={m} in-sample observations, got {y.size}")
    scale = float(np.mean(np.abs(y[m:] - y[:-m])))
    return scale if scale > 0 else None


def mase(actual, forecast, insample, season_length: int = 1) -> float | None:
    """Mean absolute scaled error; None when the scale is undefined."""
    scale = mase_scale(insample, season_length)
    if scale is None:
        return None
    return mae(actual, forecast) / scale


def coverage(actual, lower, upper) -> float:
    """Share of actual values inside [lower, upper]."""
    a = np.asarray(actual, dtype=float)
    lo = np.asarray(lower, dtype=float)
    hi = np.asarray(upper, dtype=float)
    if not (a.shape == lo.shape == hi.shape) or a.size == 0:
        raise ValueError("actual, lower and upper must be non-empty and equal length")
    return float(np.mean((a >= lo) & (a <= hi)))
