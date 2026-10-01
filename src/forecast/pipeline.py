"""One complete run: load -> profile -> backtest -> select -> refit -> forecast -> result.

This module orchestrates; every statistical decision lives in the module it calls. Nothing
here is random, so identical input gives identical output (apart from ``meta`` and the
``fit_seconds`` timings).
"""

from __future__ import annotations

import importlib.metadata
import platform
import time
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from forecast import __version__, intervals
from forecast.backtest import LEVELS, plan_backtest, resolve_horizon, run_backtest
from forecast.diagnostics import backtest_notices, check_forecastable, series_notices
from forecast.loading import load_series
from forecast.models import REGISTRY, build_model, context_from_profile, eligible_models
from forecast.profile import profile_series
from forecast.schema import (
    Artifacts,
    ForecastSummary,
    Notice,
    PointForecast,
    RefusedError,
    RunMeta,
    RunResult,
    Selection,
)
from forecast.selection import select_model

FORECAST_COLUMNS = ["series", "ds", "forecast", "lo_80", "hi_80", "lo_95", "hi_95", "model"]
_VALUE_COLUMNS = ["forecast", "lo_80", "hi_80", "lo_95", "hi_95"]
_SPEC = {s.name: s for s in REGISTRY}


@dataclass
class Outcome:
    result: RunResult
    forecast: pd.DataFrame  # FORECAST_COLUMNS
    backtest: pd.DataFrame  # backtest.csv rows
    history: pd.DataFrame  # ds, y, imputed: the regularized series the models saw


def run_forecast(
    path: str | Path,
    *,
    horizon: int | None = None,
    date: str | None = None,
    target: str | None = None,
    where: dict[str, str] | None = None,
    agg: Literal["sum", "mean"] | None = None,
    fill: Literal["interpolate", "zero"] = "interpolate",
    date_order: Literal["dmy", "mdy"] | None = None,
    build: Callable | None = None,
) -> Outcome:
    """Run the whole analysis. Raises ``NeedsInputError`` / ``RefusedError`` instead of guessing."""
    started = time.perf_counter()
    loaded = load_series(
        path, date=date, target=target, where=where, agg=agg, fill=fill, date_order=date_order
    )
    profile = profile_series(loaded)
    check_forecastable(profile)
    ctx = context_from_profile(profile)

    horizon, horizon_notices = resolve_horizon(horizon, loaded.freq, ctx.n_obs, ctx.season_length)
    plan = plan_backtest(ctx.n_obs, horizon, ctx.season_length)
    run, skipped = eligible_models(ctx)
    backtest = run_backtest(loaded.data, loaded.freq, plan, run, skipped, build=build)
    selection = select_model(backtest.summary)

    fitted_name, raw, refit_notices = fit_with_fallback(
        loaded.data, loaded.freq, backtest.summary, selection, horizon, build
    )
    frame = _forecast_frame(raw, fitted_name, _series_label(loaded.report))
    rows = backtest.frame[backtest.frame["model"] == fitted_name]
    frame, interval_info, interval_notices = intervals.calibrate(rows, frame, fitted_name)
    frame, clip_notices = _clip_non_negative(frame, profile.stats.min >= 0)

    summary = _summarize(frame, loaded.data, horizon, fitted_name, bool(clip_notices))
    warnings_ = _merge_notices(
        loaded.report.notices,
        profile.warnings,
        series_notices(profile),
        horizon_notices,
        plan.notices,
        _drop_calibrated_low_coverage(
            backtest_notices(backtest.summary, selection, profile), interval_info
        ),
        refit_notices,
        interval_notices,
        clip_notices,
    )
    result = RunResult(
        status="ok_with_warnings" if any(n.severity == "warn" for n in warnings_) else "ok",
        input=loaded.report,
        profile=profile,
        backtest=backtest.summary,
        selection=selection,
        forecast=summary,
        intervals=interval_info,
        warnings=warnings_,
        artifacts=Artifacts(
            directory="",
            profile_json="profile.json",
            result_json="result.json",
            backtest_csv="backtest.csv",
            forecast_csv="forecast.csv",
        ),
        meta=_meta(time.perf_counter() - started),
    )
    return Outcome(result=result, forecast=frame, backtest=backtest.frame, history=loaded.data)


def fit_with_fallback(
    data: pd.DataFrame,
    freq: str,
    summary,
    selection: Selection,
    horizon: int,
    build: Callable | None = None,
) -> tuple[str, pd.DataFrame, list[Notice]]:
    """Refit the selected model on all data and forecast. If that fails, try the next best.

    The order is the deterministic backtest ranking, so a fallback is as reproducible as the
    selection itself. The failure is reported, never hidden.
    """
    from statsforecast import StatsForecast

    season = {m.name: m.season_length for m in summary.models}
    sf_input = pd.DataFrame(
        {"unique_id": "series", "ds": pd.DatetimeIndex(data["ds"]), "y": data["y"].to_numpy(float)}
    )
    order = [selection.winner] + [r.name for r in selection.ranking if r.name != selection.winner]
    notices: list[Notice] = []
    for name in order:
        try:
            model = (build or build_model)(_SPEC[name], season[name])
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                raw = StatsForecast(models=[model], freq=freq, n_jobs=1).forecast(
                    h=horizon, df=sf_input, level=list(LEVELS)
                )
            needed = [name] + [f"{name}-{side}-{lv}" for lv in LEVELS for side in ("lo", "hi")]
            if any(c not in raw.columns for c in needed):
                raise ValueError("missing forecast or interval columns")
            if not np.isfinite(raw[needed].to_numpy(dtype=float)).all():
                raise ValueError("non-finite forecasts or intervals")
        except Exception as exc:  # noqa: BLE001 - any model failure falls back to the next one
            notices.append(
                Notice(
                    code="WINNER_REFIT_FAILED",
                    severity="warn",
                    message=f"{name} could not be refit on the full history ({type(exc).__name__}: {str(exc)[:120]}); "
                    "the next best model in the backtest ranking was used.",
                    details={"model": name},
                )
            )
            continue
        return name, raw, notices
    raise RefusedError("NO_VALID_MODEL", "No model could produce a final forecast.",
                       failures=[n.message for n in notices])  # fmt: skip


def _series_label(report) -> str:
    label = report.target_column
    if report.where:
        label += "[" + ",".join(f"{k}={v}" for k, v in report.where.items()) + "]"
    elif report.agg:
        label += f"[{report.agg}]"
    return label


def _forecast_frame(raw: pd.DataFrame, name: str, series: str) -> pd.DataFrame:
    out = pd.DataFrame({
        "series": series,
        "ds": raw["ds"].to_numpy(),
        "forecast": raw[name].to_numpy(dtype=float),
        **{f"{side}_{lv}": raw[f"{name}-{side}-{lv}"].to_numpy(dtype=float) for lv in LEVELS for side in ("lo", "hi")},
        "model": name,
    })  # fmt: skip
    return out[FORECAST_COLUMNS].sort_values("ds").reset_index(drop=True)


def _clip_non_negative(
    frame: pd.DataFrame, non_negative: bool
) -> tuple[pd.DataFrame, list[Notice]]:
    if not non_negative:
        return frame, []
    values = frame[_VALUE_COLUMNS]
    n_clipped = int((values < 0).to_numpy().sum())
    if not n_clipped:
        return frame, []
    out = frame.copy()
    out[_VALUE_COLUMNS] = values.clip(lower=0.0)
    notice = Notice(code="FORECAST_CLIPPED", severity="info",
                    message=f"{n_clipped} forecast or interval values below zero were raised to zero because the "
                            "history never goes negative.",
                    details={"n": n_clipped})  # fmt: skip
    return out, [notice]


def _summarize(
    frame: pd.DataFrame, data: pd.DataFrame, horizon: int, model: str, clipped: bool
) -> ForecastSummary:
    total = float(frame["forecast"].sum())
    previous = float(data["y"].iloc[-horizon:].sum())
    return ForecastSummary(
        model=model,
        horizon=horizon,
        start=pd.Timestamp(frame["ds"].iloc[0]).isoformat(),
        end=pd.Timestamp(frame["ds"].iloc[-1]).isoformat(),
        first=_point(frame.iloc[0]),
        last=_point(frame.iloc[-1]),
        last_observed=float(data["y"].iloc[-1]),
        mean=float(frame["forecast"].mean()),
        total=total,
        previous_total=previous,
        change_vs_prior=(total / previous - 1) if previous != 0 else None,
        clipped_at_zero=clipped,
    )


def _point(row: pd.Series) -> PointForecast:
    return PointForecast(
        ds=pd.Timestamp(row["ds"]).isoformat(),
        **{c: float(row[c]) for c in ("forecast", "lo_80", "hi_80", "lo_95", "hi_95")},
    )


def _drop_calibrated_low_coverage(notices: list[Notice], info) -> list[Notice]:
    if info.method != "calibrated":
        return notices
    return [n for n in notices if n.code != "LOW_COVERAGE"]  # superseded by INTERVALS_CALIBRATED


def _merge_notices(*groups: list[Notice]) -> list[Notice]:
    seen, out = set(), []
    for group in groups:
        for n in group:
            key = (n.code, n.message)
            if key not in seen:
                seen.add(key)
                out.append(n)
    return out


def _meta(elapsed: float) -> RunMeta:
    return RunMeta(
        forecast_version=__version__,
        statsforecast_version=importlib.metadata.version("statsforecast"),
        pandas_version=pd.__version__,
        python_version=platform.python_version(),
        elapsed_seconds=round(elapsed, 2),
    )
