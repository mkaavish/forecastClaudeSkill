"""Deterministic statistical profile of a loaded series.

Claude reads this report instead of computing anything itself. Every number here is a fact
about the observed data; nothing is a forecast and no model is chosen.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from scipy import stats as sps
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.stattools import adfuller

from forecast.loading import LoadedSeries
from forecast.schema import (
    Intermittency,
    Notice,
    Outlier,
    OutlierSummary,
    ProfileReport,
    Seasonality,
    SeasonalityCandidate,
    Stats,
    Trend,
)

# Candidate seasonal periods per base frequency. Longer ones (365, 168) are only tested when
# at least MIN_CYCLES full cycles exist.
SEASONAL_PERIODS: dict[str, list[int]] = {
    "h": [24, 168],
    "D": [7, 365],
    "B": [5],
    "W": [52],
    "MS": [12],
    "ME": [12],
    "QS": [4],
    "QE": [4],
    "YS": [],
    "YE": [],
}
MIN_CYCLES = 2
SEASONAL_P_VALUE = 1e-3  # F-test across seasonal positions; 0/500 false positives on pure noise
SEASONAL_MIN_STRENGTH = 0.10
ZERO_HEAVY_FRACTION = 0.30
ADI_CUTOFF, CV2_CUTOFF = 1.32, 0.49  # Syntetos-Boylan demand classification
OUTLIER_Z = 3.5
OUTLIER_WINDOW = 7
TREND_P_VALUE = 0.01
TREND_MIN_RELATIVE_CHANGE = 0.05
TREND_MIN_OBS = 8
THEIL_SEN_MAX_POINTS = 2000


def profile_series(loaded: LoadedSeries) -> ProfileReport:
    y = loaded.data["y"].to_numpy(dtype=float)
    ds = pd.DatetimeIndex(loaded.data["ds"])
    base_freq = loaded.freq.split("-")[0]

    stats = _stats(y)
    constant = bool(np.ptp(y) == 0)
    near_constant = (not constant) and _near_constant(y)
    seasonality = _seasonality(y, base_freq, constant)
    intermittency = _intermittency(y, stats)
    outliers = _outliers(y, ds, seasonality.season_length, constant)
    # Trend is judged on the seasonally adjusted series so seasonal swings do not mask or fake it.
    adjusted = (
        y - _stl(y, seasonality.season_length).seasonal if seasonality.season_length > 1 else y
    )
    trend = _trend(adjusted, stats)

    report = ProfileReport(
        input=loaded.report,
        stats=stats,
        constant=constant,
        near_constant=near_constant,
        intermittency=intermittency,
        outliers=outliers,
        trend=trend,
        seasonality=seasonality,
    )
    report.warnings = _notices(report)
    return report


# --------------------------------------------------------------------------- descriptive


def _stats(y: np.ndarray) -> Stats:
    q25, med, q75 = np.quantile(y, [0.25, 0.5, 0.75])
    mean = float(np.mean(y))
    std = float(np.std(y, ddof=1)) if len(y) > 1 else 0.0
    return Stats(
        n=len(y),
        mean=mean,
        std=std,
        min=float(np.min(y)),
        q25=float(q25),
        median=float(med),
        q75=float(q75),
        max=float(np.max(y)),
        zero_fraction=float(np.mean(y == 0)),
        n_negative=int(np.sum(y < 0)),
        cv=std / abs(mean) if mean != 0 else None,
    )


def _near_constant(y: np.ndarray) -> bool:
    values, counts = np.unique(y, return_counts=True)
    mode = values[np.argmax(counts)]
    return bool(counts.max() / len(y) >= 0.95 and mode != 0)  # a zero mode is intermittency


def _intermittency(y: np.ndarray, stats: Stats) -> Intermittency:
    if stats.n_negative or stats.min < 0:
        return Intermittency(
            applicable=False, adi=None, cv2=None, demand_class=None, zero_heavy=False
        )
    nonzero = y[y > 0]
    zero_heavy = stats.zero_fraction >= ZERO_HEAVY_FRACTION
    if len(nonzero) == 0:
        return Intermittency(
            applicable=True, adi=None, cv2=None, demand_class=None, zero_heavy=zero_heavy
        )
    adi = len(y) / len(nonzero)
    cv2 = float((np.std(nonzero) / np.mean(nonzero)) ** 2)
    if adi < ADI_CUTOFF:
        label = "smooth" if cv2 < CV2_CUTOFF else "erratic"
    else:
        label = "intermittent" if cv2 < CV2_CUTOFF else "lumpy"
    return Intermittency(
        applicable=True,
        adi=round(adi, 4),
        cv2=round(cv2, 4),
        demand_class=label,
        zero_heavy=zero_heavy,
    )


# --------------------------------------------------------------------------- trend


def _trend(y: np.ndarray, stats: Stats) -> Trend:
    """Monotonic trend, reported only when it is distinguishable from a random walk.

    Kendall's tau alone flags ~88% of pure random walks as trending (it assumes independent
    errors). So a trend must also pass one of two guards (measured over 60 seeds each):

    * a drift test on first differences (random walks have mean-zero differences), or
    * an ADF unit-root test with a trend term (trend-stationary series reject a unit root).

    The drift test alone misses noisy trends (0% power at slope 1, noise 30, n=730) because
    differencing amplifies noise; the ADF test recovers them (100%). Random-walk false
    positives stay at 2-3%.
    """
    n = len(y)
    none = Trend(direction="none", slope_per_period=None, relative_change=None, p_value=None,
                 drift_p_value=None, adf_p_value=None)  # fmt: skip
    if n < TREND_MIN_OBS:
        return none.model_copy(update={"direction": "insufficient_data"})
    if np.ptp(y) == 0:
        return none
    t = np.arange(n, dtype=float)
    idx = np.unique(np.linspace(0, n - 1, min(n, THEIL_SEN_MAX_POINTS)).astype(int))
    slope = float(sps.theilslopes(y[idx], t[idx])[0])
    p_value = float(sps.kendalltau(t, y).pvalue)
    diffs = np.diff(y)
    drift_p = float(sps.ttest_1samp(diffs, 0.0).pvalue) if np.std(diffs) > 0 else 0.0
    adf_p = _adf_p_value(y)
    scale = abs(stats.median) or abs(stats.mean) or 1.0
    relative = slope * (n - 1) / scale
    not_random_walk = drift_p < TREND_P_VALUE or (adf_p is not None and adf_p < TREND_P_VALUE)
    if p_value < TREND_P_VALUE and not_random_walk and abs(relative) >= TREND_MIN_RELATIVE_CHANGE:
        direction = "positive" if slope > 0 else "negative"
    else:
        direction = "none"
    return Trend(direction=direction, slope_per_period=slope, relative_change=float(relative),
                 p_value=p_value, drift_p_value=drift_p, adf_p_value=adf_p)  # fmt: skip


def _adf_p_value(y: np.ndarray) -> float | None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return float(adfuller(y, regression="ct", autolag="AIC")[1])
    except (ValueError, np.linalg.LinAlgError):  # too short or degenerate
        return None


# --------------------------------------------------------------------------- seasonality


def _stl(y: np.ndarray, period: int, robust: bool = True):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return STL(y, period=period, robust=robust).fit()


def _seasonal_evidence(y: np.ndarray, period: int) -> tuple[float, float, float, np.ndarray]:
    """(strength, p_value, trend_strength, seasonal_component) for one candidate period."""
    fit = _stl(y, period)
    resid_var = np.var(fit.resid)
    strength = max(0.0, 1.0 - resid_var / np.var(fit.seasonal + fit.resid))
    trend_strength = max(0.0, 1.0 - resid_var / np.var(fit.trend + fit.resid))
    detrended = y - fit.trend
    groups = [detrended[i::period] for i in range(period)]
    p_value = float(sps.f_oneway(*groups).pvalue)
    return (
        float(strength),
        p_value if np.isfinite(p_value) else 1.0,
        float(trend_strength),
        fit.seasonal,
    )


def _seasonality(y: np.ndarray, base_freq: str, constant: bool) -> Seasonality:
    n = len(y)
    candidates: list[SeasonalityCandidate] = []
    seasonal_parts: dict[int, np.ndarray] = {}
    trend_strength: float | None = None
    for period in SEASONAL_PERIODS.get(base_freq, []):
        cycles = n / period
        if constant:
            note = "constant series"
        elif cycles < MIN_CYCLES:
            note = f"fewer than {MIN_CYCLES} full cycles ({cycles:.1f})"
        else:
            note = ""
        if note:
            candidates.append(
                SeasonalityCandidate(
                    period=period, cycles=round(cycles, 2), tested=False, strength=None,
                    p_value=None, detected=False, note=note,
                )
            )  # fmt: skip
            continue
        strength, p_value, ts_strength, seasonal = _seasonal_evidence(y, period)
        seasonal_parts[period] = seasonal
        if period == SEASONAL_PERIODS[base_freq][0]:
            trend_strength = ts_strength
        candidates.append(
            SeasonalityCandidate(
                period=period,
                cycles=round(cycles, 2),
                tested=True,
                strength=round(strength, 4),
                p_value=p_value,
                detected=bool(p_value < SEASONAL_P_VALUE and strength >= SEASONAL_MIN_STRENGTH),
            )
        )
    detected = [c for c in candidates if c.detected]
    if not detected:
        return Seasonality(
            candidates=candidates, season_length=1, multiple=False, trend_strength=trend_strength
        )

    # The shortest detected period is the one a model can actually use (a longer period such
    # as 168 contains every repeat of 24, so it always "explains" the shorter one). Longer
    # periods are then checked for independent structure after removing the primary.
    primary = min(detected, key=lambda c: c.period)
    adjusted = y - seasonal_parts[primary.period]
    multiple = False
    for cand in detected:
        if cand.period == primary.period:
            continue
        _, p_after, _, _ = _seasonal_evidence(adjusted, cand.period)
        cand.independent = bool(p_after < SEASONAL_P_VALUE)
        cand.note = (
            f"still significant after removing period {primary.period}"
            if cand.independent
            else f"explained by period {primary.period}"
        )
        multiple = multiple or cand.independent
    return Seasonality(
        candidates=candidates,
        season_length=primary.period,
        multiple=multiple,
        trend_strength=trend_strength,
    )


# --------------------------------------------------------------------------- outliers


def _outliers(
    y: np.ndarray, ds: pd.DatetimeIndex, season_length: int, constant: bool
) -> OutlierSummary:
    if constant or len(y) < 5:
        return OutlierSummary(method="none", n_outliers=0, fraction=0.0, top=[])
    if season_length > 1:
        # Non-robust fit on purpose: robust STL shrinks inlier residuals, which makes the MAD
        # tiny and flags ~7% of clean Gaussian data (measured); non-robust flags ~0.1%.
        residual = _stl(y, season_length, robust=False).resid
        method = "stl_residual_mad"
    else:
        residual = (
            y - pd.Series(y).rolling(OUTLIER_WINDOW, center=True, min_periods=1).median().to_numpy()
        )
        method = "rolling_median_mad"
    center = np.median(residual)
    mad = np.median(np.abs(residual - center))
    if mad == 0:
        return OutlierSummary(
            method=f"{method} (MAD=0, skipped)", n_outliers=0, fraction=0.0, top=[]
        )
    z = 0.6745 * (residual - center) / mad
    flagged = np.flatnonzero(np.abs(z) > OUTLIER_Z)
    order = flagged[np.argsort(-np.abs(z[flagged]))][:10]
    return OutlierSummary(
        method=method,
        n_outliers=len(flagged),
        fraction=round(len(flagged) / len(y), 4),
        top=[
            Outlier(ds=ds[i].isoformat(), value=float(y[i]), robust_z=round(float(z[i]), 2))
            for i in order
        ],
    )


# --------------------------------------------------------------------------- notices


def _notices(r: ProfileReport) -> list[Notice]:
    out: list[Notice] = []
    if r.constant:
        out.append(Notice(code="CONSTANT_SERIES", severity="warn",
                          message="Every observation has the same value; there is nothing to forecast."))  # fmt: skip
    elif r.near_constant:
        out.append(Notice(code="NEAR_CONSTANT", severity="warn",
                          message="At least 95% of observations share one value; forecasts will be nearly flat."))  # fmt: skip
    if r.intermittency.zero_heavy:
        out.append(Notice(code="INTERMITTENT", severity="warn",
                          message=f"{r.stats.zero_fraction:.0%} of observations are zero (intermittent demand). "
                                  "Standard models (ETS/ARIMA) handle this poorly.",
                          details={"zero_fraction": round(r.stats.zero_fraction, 4),
                                   "demand_class": r.intermittency.demand_class}))  # fmt: skip
    if r.stats.n_negative:
        out.append(Notice(code="NEGATIVE_VALUES", severity="info",
                          message=f"{r.stats.n_negative} negative values; forecasts will not be clipped at zero.",
                          details={"n": r.stats.n_negative}))  # fmt: skip
    if r.outliers.n_outliers:
        out.append(Notice(code="OUTLIERS", severity="warn" if r.outliers.fraction >= 0.01 else "info",
                          message=f"{r.outliers.n_outliers} potential outliers flagged (kept in the data).",
                          details={"n": r.outliers.n_outliers, "fraction": r.outliers.fraction}))  # fmt: skip
    tested = [c for c in r.seasonality.candidates if c.tested]
    if not r.constant:
        if not tested:
            out.append(Notice(code="SEASONALITY_UNTESTED", severity="info",
                              message="Too little history (or no standard period) to test for seasonality."))  # fmt: skip
        elif r.seasonality.season_length == 1:
            out.append(Notice(code="NO_SEASONALITY", severity="info",
                              message="No statistically significant seasonality at the tested periods "
                                      f"({', '.join(str(c.period) for c in tested)})."))  # fmt: skip
    if r.seasonality.multiple:
        out.append(Notice(code="MULTIPLE_SEASONALITY", severity="warn",
                          message="More than one seasonal pattern is present; V1 models only the strongest "
                                  f"(period {r.seasonality.season_length}).",
                          details={"periods": [c.period for c in r.seasonality.candidates if c.detected]}))  # fmt: skip
    return out
