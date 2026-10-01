"""Rolling-origin backtest planning.

Windows are expanding-train / fixed-horizon / non-overlapping test blocks packed against the
end of the series:

    TRAIN ───────────── TEST
    TRAIN ───────────────── TEST
    TRAIN ───────────────────── TEST

Planning is pure arithmetic over the series length. Execution fits each model in its own
StatsForecast call so one failing model cannot take the others down.
"""

from __future__ import annotations

import math
import time
import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd

from forecast import metrics
from forecast.models import Eligibility, ModelSpec, build_model
from forecast.schema import (
    BacktestPlan,
    BacktestSummary,
    BacktestWindow,
    ModelBacktest,
    ModelMetrics,
    Notice,
    RefusedError,
)

MIN_WINDOWS = 3
MAX_WINDOWS = 5
MIN_TRAIN_FLOOR = 24
LONG_HORIZON_FRACTION = 0.20  # warn when horizon > this share of the history

DEFAULT_HORIZONS = {
    "h": 24,
    "D": 28,
    "B": 20,
    "W": 13,
    "MS": 12,
    "ME": 12,
    "QS": 4,
    "QE": 4,
    "YS": 3,
    "YE": 3,
}


def min_train_size(season_length: int) -> int:
    """Shortest training window: two seasonal cycles, and never fewer than 24 points."""
    return max(2 * max(season_length, 1), MIN_TRAIN_FLOOR)


def max_full_horizon(n_obs: int, season_length: int) -> int:
    """Longest horizon that still yields MIN_WINDOWS non-overlapping windows."""
    return (n_obs - min_train_size(season_length)) // MIN_WINDOWS


def resolve_horizon(
    requested: int | None, frequency: str, n_obs: int, season_length: int
) -> tuple[int, list[Notice]]:
    """Pick the forecast horizon: the user's, or a frequency default capped to what history supports."""
    if requested is not None:
        if requested < 1:
            raise RefusedError("BAD_ARGUMENT", f"--horizon must be at least 1, got {requested}.")
        return requested, []
    default = DEFAULT_HORIZONS.get(frequency.split("-")[0], 12)
    cap = max_full_horizon(n_obs, season_length)
    if cap >= default:
        return default, []
    if cap < 1:
        raise RefusedError(
            "INSUFFICIENT_DATA",
            f"{n_obs} observations are too few to backtest even a 1-step forecast; "
            f"need at least {min_train_size(season_length) + MIN_WINDOWS}.",
            n_obs=n_obs,
            required=min_train_size(season_length) + MIN_WINDOWS,
        )
    notice = Notice(code="HORIZON_DEFAULT_REDUCED", severity="info",
                    message=f"Default horizon of {default} reduced to {cap} so that history can back-test it.",
                    details={"default": default, "used": cap})  # fmt: skip
    return cap, [notice]


def plan_backtest(n_obs: int, horizon: int, season_length: int = 1) -> BacktestPlan:
    """Lay out the rolling-origin windows, shortening the backtest horizon only as a last resort.

    * Preferred: backtest at the full ``horizon`` with 3 to 5 windows.
    * If history cannot support 3 windows at that horizon, shorten the backtest horizon down
      to a floor of ``max(season_length, ceil(horizon / 2))`` and say so.
    * Below that floor the evidence would not describe the forecast being asked for: refuse.
    """
    if horizon < 1:
        raise RefusedError("BAD_ARGUMENT", f"horizon must be at least 1, got {horizon}.")
    min_train = min_train_size(season_length)
    notices: list[Notice] = []
    supported = (n_obs - min_train) // MIN_WINDOWS  # longest horizon with 3 windows

    if supported >= horizon:
        h_bt = horizon
    else:
        floor = min(horizon, max(season_length, math.ceil(horizon / 2)))
        if supported < 1:
            raise RefusedError(
                "INSUFFICIENT_DATA",
                f"{n_obs} observations are too few to backtest: need at least "
                f"{min_train + MIN_WINDOWS} (two seasonal cycles or 24 points, plus 3 test windows).",
                n_obs=n_obs,
                required=min_train + MIN_WINDOWS,
            )
        if supported < floor:
            raise RefusedError(
                "HORIZON_TOO_LONG",
                f"A {horizon}-step forecast cannot be validated with {n_obs} observations: "
                f"at least {min_train + MIN_WINDOWS * floor} are needed, or use a horizon of "
                f"{supported} or less.",
                n_obs=n_obs,
                horizon=horizon,
                max_horizon=supported,
                required=min_train + MIN_WINDOWS * floor,
            )
        h_bt = supported
        notices.append(Notice(code="BACKTEST_HORIZON_SHORTENED", severity="warn",
                              message=f"History is too short to back-test {horizon} steps ahead; models were "
                                      f"scored on {h_bt}-step forecasts instead. Accuracy at the full horizon "
                                      "is likely worse than measured.",
                              details={"horizon": horizon, "backtest_horizon": h_bt}))  # fmt: skip

    n_windows = min(MAX_WINDOWS, (n_obs - min_train) // h_bt)
    windows = []
    for w in range(n_windows):
        test_start = n_obs - (n_windows - w) * h_bt
        windows.append(BacktestWindow(index=w, train_end=test_start, test_start=test_start,
                                      test_end=test_start + h_bt))  # fmt: skip

    if horizon > LONG_HORIZON_FRACTION * n_obs:
        notices.append(Notice(code="HORIZON_LONG", severity="warn",
                              message=f"The {horizon}-step horizon is more than {LONG_HORIZON_FRACTION:.0%} of "
                                      f"the {n_obs} observations of history; long-range forecasts are unreliable.",
                              details={"horizon": horizon, "n_obs": n_obs}))  # fmt: skip
    if n_windows < MAX_WINDOWS:
        notices.append(Notice(code="FEW_BACKTEST_WINDOWS", severity="info",
                              message=f"Model selection rests on {n_windows} backtest windows; "
                                      "with so few, rankings are noisy.",
                              details={"n_windows": n_windows}))  # fmt: skip
    return BacktestPlan(
        horizon=horizon,
        backtest_horizon=h_bt,
        n_windows=n_windows,
        step=h_bt,
        min_train=min_train,
        season_length=season_length,
        shortened=h_bt < horizon,
        windows=windows,
        notices=notices,
    )


# --------------------------------------------------------------------------- execution

LEVELS = (80, 95)
FRAME_COLUMNS = [
    "model",
    "window",
    "cutoff",
    "ds",
    "step",
    "y",
    "yhat",
    "lo_80",
    "hi_80",
    "lo_95",
    "hi_95",
]


@dataclass
class BacktestResult:
    summary: BacktestSummary
    frame: pd.DataFrame  # long format, one row per (model, window, step); see FRAME_COLUMNS


def run_backtest(
    data: pd.DataFrame,
    freq: str,
    plan: BacktestPlan,
    run: list[tuple[ModelSpec, Eligibility]],
    skipped: list[tuple[ModelSpec, Eligibility]] = (),
    build=None,
) -> BacktestResult:
    """Cross-validate every model in ``run`` over the planned windows.

    ``data`` has columns ``ds`` and ``y`` (regular, no gaps). A model that raises, or returns
    non-finite forecasts, is recorded as failed and excluded; the others still run.
    """
    y = data["y"].to_numpy(dtype=float)
    ds = pd.DatetimeIndex(data["ds"])
    expected_cutoffs = [ds[w.train_end - 1] for w in plan.windows]
    scale, scale_source = _mase_scale(y, plan)
    sf_input = pd.DataFrame({"unique_id": "series", "ds": ds, "y": y})

    records: list[ModelBacktest] = []
    frames: list[pd.DataFrame] = []
    for spec, verdict in run:
        started = time.perf_counter()
        try:
            raw = _cross_validate(sf_input, freq, spec, verdict.season_length, plan, build)
        except Exception as exc:  # noqa: BLE001 - any model failure must be isolated
            records.append(ModelBacktest(
                name=spec.name, kind=spec.kind, status="failed", season_length=verdict.season_length,
                reason=f"{type(exc).__name__}: {str(exc)[:200]}",
                fit_seconds=round(time.perf_counter() - started, 3),
            ))  # fmt: skip
            continue
        elapsed = round(time.perf_counter() - started, 3)
        frame = _to_frame(
            raw, spec.name, expected_cutoffs
        )  # engine invariant: raises if misaligned
        if not np.isfinite(frame[["yhat", "lo_80", "hi_80", "lo_95", "hi_95"]].to_numpy()).all():
            records.append(ModelBacktest(
                name=spec.name, kind=spec.kind, status="failed", season_length=verdict.season_length,
                reason="non-finite forecasts or intervals", fit_seconds=elapsed,
            ))  # fmt: skip
            continue
        frames.append(frame)
        records.append(ModelBacktest(
            name=spec.name, kind=spec.kind, status="ok", season_length=verdict.season_length,
            reason=verdict.reason, fit_seconds=elapsed, metrics=_score(frame, scale, plan),
        ))  # fmt: skip
    for spec, verdict in skipped:
        records.append(ModelBacktest(name=spec.name, kind=spec.kind, status="skipped",
                                     season_length=verdict.season_length, reason=verdict.reason))  # fmt: skip

    summary = BacktestSummary(plan=plan, mase_scale=scale, mase_scale_source=scale_source,
                              levels=list(LEVELS), models=records)  # fmt: skip
    frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=FRAME_COLUMNS)
    return BacktestResult(summary=summary, frame=frame)


def _cross_validate(
    sf_input: pd.DataFrame,
    freq: str,
    spec: ModelSpec,
    season_length: int,
    plan: BacktestPlan,
    build=None,
):
    from statsforecast import StatsForecast

    model = (build or build_model)(
        spec, season_length
    )  # resolved at call time so tests can patch it
    sf = StatsForecast(models=[model], freq=freq, n_jobs=1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        raw = sf.cross_validation(
            h=plan.backtest_horizon,
            df=sf_input,
            n_windows=plan.n_windows,
            step_size=plan.step,
            level=list(LEVELS),
        )
    needed = [spec.name] + [f"{spec.name}-{side}-{lv}" for lv in LEVELS for side in ("lo", "hi")]
    missing = [c for c in needed if c not in raw.columns]
    if missing:
        raise ValueError(f"model returned no {', '.join(missing)}")
    return raw


def _to_frame(raw: pd.DataFrame, name: str, expected_cutoffs: list[pd.Timestamp]) -> pd.DataFrame:
    cutoffs = sorted(raw["cutoff"].unique())
    if [pd.Timestamp(c) for c in cutoffs] != expected_cutoffs:
        raise RuntimeError(
            f"StatsForecast windows {cutoffs} do not match the plan {expected_cutoffs}"
        )
    window = raw["cutoff"].map({c: i for i, c in enumerate(cutoffs)})
    out = pd.DataFrame({
        "model": name,
        "window": window.to_numpy(),
        "cutoff": raw["cutoff"].to_numpy(),
        "ds": raw["ds"].to_numpy(),
        "y": raw["y"].to_numpy(dtype=float),
        "yhat": raw[name].to_numpy(dtype=float),
        **{f"{side}_{lv}": raw[f"{name}-{side}-{lv}"].to_numpy(dtype=float) for lv in LEVELS for side in ("lo", "hi")},
    })  # fmt: skip
    out = out.sort_values(["window", "ds"]).reset_index(drop=True)
    out["step"] = out.groupby("window").cumcount() + 1
    return out[FRAME_COLUMNS]


def _mase_scale(y: np.ndarray, plan: BacktestPlan):
    """One constant scale for all windows (it never changes the ranking, only the units).

    Uses the first window's training data so no test observation leaks into it; falls back to
    everything before the final test block if that stretch is flat.
    """
    for end, label in (
        (plan.windows[0].train_end, "initial_training"),
        (plan.windows[-1].train_end, "pre_final_window"),
    ):
        scale = metrics.mase_scale(y[:end], plan.season_length)
        if scale is not None:
            return scale, label
    return None, "undefined"


def _score(frame: pd.DataFrame, scale: float | None, plan: BacktestPlan) -> ModelMetrics:
    a, f = frame["y"].to_numpy(), frame["yhat"].to_numpy()
    window_mae = [metrics.mae(g["y"], g["yhat"]) for _, g in frame.groupby("window")]
    return ModelMetrics(
        mae=metrics.mae(a, f),
        rmse=metrics.rmse(a, f),
        smape=metrics.smape(a, f),
        mase=metrics.mae(a, f) / scale if scale else None,
        coverage_80=metrics.coverage(a, frame["lo_80"], frame["hi_80"]),
        coverage_95=metrics.coverage(a, frame["lo_95"], frame["hi_95"]),
        mean_width_80=float(np.mean(frame["hi_80"] - frame["lo_80"])),
        window_mae=window_mae,
        window_mase=[m / scale for m in window_mae] if scale else None,
    )
