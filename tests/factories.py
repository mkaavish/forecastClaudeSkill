"""Hand-built backtest summaries, so selection and diagnostics rules can be tested exactly."""

from __future__ import annotations

from forecast.backtest import plan_backtest
from forecast.models import REGISTRY
from forecast.schema import BacktestSummary, ModelBacktest, ModelMetrics

KIND = {spec.name: spec.kind for spec in REGISTRY}
SCALE = 2.0  # mase_scale used by every factory summary: mae == mase * SCALE


def metrics(mase=1.0, window_mae=None, coverage_80=0.8, width=1.0, n_windows=5):
    mae = None if mase is None else mase * SCALE
    return ModelMetrics(
        mae=mae if mae is not None else 1.0,
        rmse=1.0 if mae is None else mae * 1.2,
        smape=10.0,
        mase=mase,
        coverage_80=coverage_80,
        coverage_95=min(1.0, coverage_80 + 0.1),
        mean_width_80=width,
        window_mae=window_mae if window_mae is not None else [mae or 1.0] * n_windows,
        window_mase=None
        if mase is None
        else [w / SCALE for w in (window_mae or [mae] * n_windows)],
    )


def model(name, mase=1.0, status="ok", reason="", season_length=1, **kw):
    ok = status == "ok"
    return ModelBacktest(
        name=name,
        kind=KIND[name],
        status=status,
        season_length=season_length,
        reason=reason,
        metrics=metrics(mase, **kw) if ok else None,
    )


def summary(*models, n_obs=300, horizon=14, season=7, scale=SCALE):
    plan = plan_backtest(n_obs, horizon, season)
    return BacktestSummary(
        plan=plan,
        mase_scale=scale,
        mase_scale_source="initial_training" if scale else "undefined",
        levels=[80, 95],
        models=list(models),
    )
