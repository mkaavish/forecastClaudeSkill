"""Seeded synthetic series whose true behaviour is known.

Each generator returns a DataFrame with ``date`` and ``value`` columns. The ground truth
(trend slope, seasonal period, noise level) is stated in the docstring so tests can assert
sensible behaviour rather than mere absence of crashes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _frame(values: np.ndarray, start: str = "2024-01-01", freq: str = "D") -> pd.DataFrame:
    return pd.DataFrame(
        {"date": pd.date_range(start, periods=len(values), freq=freq), "value": values}
    )


def linear_trend(
    n: int = 200, slope: float = 2.0, intercept: float = 100.0, noise: float = 1.0, seed: int = 0
):
    """value = intercept + slope * t + N(0, noise). No seasonality."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    return _frame(intercept + slope * t + rng.normal(0, noise, n))


def weekly_seasonality(
    n: int = 210, amplitude: float = 20.0, level: float = 200.0, noise: float = 2.0, seed: int = 0
):
    """Daily, period 7, no trend: level + amplitude * sin(2*pi*t/7) + N(0, noise)."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    return _frame(level + amplitude * np.sin(2 * np.pi * t / 7) + rng.normal(0, noise, n))


def trend_seasonality(
    n: int = 280, slope: float = 0.5, amplitude: float = 15.0, noise: float = 2.0, seed: int = 0
):
    """Daily: 100 + slope * t + amplitude * sin(2*pi*t/7) + N(0, noise)."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    return _frame(100 + slope * t + amplitude * np.sin(2 * np.pi * t / 7) + rng.normal(0, noise, n))


def white_noise(n: int = 200, level: float = 50.0, noise: float = 5.0, seed: int = 0):
    """Pure noise around a constant mean: nothing to forecast beyond the mean."""
    rng = np.random.default_rng(seed)
    return _frame(level + rng.normal(0, noise, n))


def random_walk(n: int = 200, step: float = 1.0, seed: int = 0):
    """Cumulative sum of N(0, step): Naive is the optimal point forecast."""
    rng = np.random.default_rng(seed)
    return _frame(100 + np.cumsum(rng.normal(0, step, n)))


def constant(n: int = 100, level: float = 5.0):
    """Exactly constant: not forecastable in any meaningful statistical sense."""
    return _frame(np.full(n, level))


def zero_heavy(n: int = 200, p_zero: float = 0.7, seed: int = 0):
    """Intermittent demand: ~70% zeros, otherwise Poisson(6) + 1."""
    rng = np.random.default_rng(seed)
    demand = rng.poisson(6, n) + 1
    return _frame(np.where(rng.random(n) < p_zero, 0, demand).astype(float))


def level_shift(
    n: int = 200, shift_at: int = 120, shift: float = 40.0, noise: float = 2.0, seed: int = 0
):
    """Constant level that jumps by ``shift`` at index ``shift_at`` (structural break)."""
    rng = np.random.default_rng(seed)
    base = np.where(np.arange(n) < shift_at, 100.0, 100.0 + shift)
    return _frame(base + rng.normal(0, noise, n))


def with_missing_timestamps(df: pd.DataFrame, drop_every: int = 25) -> pd.DataFrame:
    """Remove whole rows (the timestamp disappears) at regular positions."""
    keep = np.arange(len(df)) % drop_every != drop_every - 1
    return df.loc[keep].reset_index(drop=True)


def with_missing_values(df: pd.DataFrame, positions: list[int]) -> pd.DataFrame:
    """Blank the value (the timestamp stays) at the given row positions."""
    out = df.copy()
    out.loc[positions, "value"] = np.nan
    return out
