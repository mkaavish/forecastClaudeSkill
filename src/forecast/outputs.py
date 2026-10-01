"""Writers for result files.

A run directory contains:

* ``result.json``   - the validated RunResult (everything Claude or a script needs)
* ``profile.json``  - the dataset profile on its own
* ``forecast.csv``  - ``series, ds, forecast, lo_80, hi_80, lo_95, hi_95, model``
* ``backtest.csv``  - one row per (model, window, step): the audit trail behind every metric
* ``forecast.png``  - the chart (omitted, with a ``PLOT_FAILED`` warning, if drawing fails)

``text_summary`` renders a result as plain text using only values found in ``result.json``.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from forecast.backtest import FRAME_COLUMNS
from forecast.pipeline import FORECAST_COLUMNS, Outcome
from forecast.schema import Notice, RunResult

_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


def write_backtest_csv(frame: pd.DataFrame, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame[FRAME_COLUMNS].to_csv(out, index=False, date_format=_DATE_FORMAT)
    return out


def write_forecast_csv(frame: pd.DataFrame, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame[FORECAST_COLUMNS].to_csv(out, index=False, date_format=_DATE_FORMAT)
    return out


def write_artifacts(outcome: Outcome, directory: str | Path) -> RunResult:
    """Write every file of a successful run; returns the result with its artifact paths filled in."""
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    artifacts = outcome.result.artifacts.model_copy(update={"directory": str(out.resolve())})
    result = outcome.result
    plot_name = "forecast.png"
    try:
        from forecast.plot import plot_forecast

        plot_forecast(outcome, out / plot_name)
        artifacts = artifacts.model_copy(update={"plot": plot_name})
    except Exception as exc:  # noqa: BLE001 - a chart problem must never lose the forecast
        notice = Notice(code="PLOT_FAILED", severity="warn",
                        message=f"The chart could not be drawn ({type(exc).__name__}: {str(exc)[:120]}).")  # fmt: skip
        result = result.model_copy(
            update={"warnings": [*result.warnings, notice], "status": "ok_with_warnings"}
        )
    result = result.model_copy(update={"artifacts": artifacts})
    write_forecast_csv(outcome.forecast, out / artifacts.forecast_csv)
    write_backtest_csv(outcome.backtest, out / artifacts.backtest_csv)
    (out / artifacts.profile_json).write_text(result.profile.model_dump_json(indent=2) + "\n")
    (out / artifacts.result_json).write_text(result.model_dump_json(indent=2) + "\n")
    return result


# --------------------------------------------------------------------------- text summary

_SEASON_NAMES = {
    ("h", 24): "daily", ("h", 168): "weekly", ("D", 7): "weekly", ("D", 365): "yearly", ("B", 5): "weekly",
    ("W", 52): "yearly", ("MS", 12): "yearly", ("ME", 12): "yearly", ("QS", 4): "yearly", ("QE", 4): "yearly",
}  # fmt: skip


def _num(x: float) -> str:
    """One formatting rule for every number: grouped integers when large, 3 significant digits when small."""
    return f"{x:,.0f}" if abs(x) >= 1000 else f"{x:,.1f}" if abs(x) >= 100 else f"{x:.3g}"


def _pattern(result: RunResult) -> str:
    seas, trend = result.profile.seasonality, result.profile.trend
    parts = []
    if seas.season_length > 1:
        base = result.input.frequency.split("-")[0]
        name = _SEASON_NAMES.get((base, seas.season_length), f"period-{seas.season_length}")
        strength = next(
            (c.strength for c in seas.candidates if c.period == seas.season_length), None
        )
        parts.append(
            f"{name} seasonality (period {seas.season_length}"
            + (f", strength {strength:.2f})" if strength is not None else ")")
        )
    else:
        parts.append("no significant seasonality")
    if trend.direction in ("positive", "negative"):
        word = "upward" if trend.direction == "positive" else "downward"
        parts.append(f"{word} trend ({trend.relative_change:+.0%} over the history)")
    elif trend.direction == "none":
        parts.append("no distinguishable trend")
    if result.profile.intermittency.zero_heavy:
        parts.append(f"intermittent demand ({result.profile.stats.zero_fraction:.0%} zeros)")
    return "; ".join(parts)


def text_summary(result: RunResult) -> str:
    """Plain-text report. Every number comes straight from ``result``; nothing is recomputed."""
    f, sel, inp = result.forecast, result.selection, result.input
    chosen = next(m for m in result.backtest.models if m.name == f.model)
    lines = [f"FORECAST ANALYSIS: {inp.target_column}", ""]
    rows = [
        ("Horizon", f"{f.horizon} {inp.frequency_name} periods ({f.start[:10]} to {f.end[:10]})"),
        ("Pattern", _pattern(result)),
        (
            "Model",
            f.model + ("" if f.model == sel.winner else f" (fallback; {sel.winner} was selected)"),
        ),
        ("Why", sel.explanation),
    ]
    if chosen.metrics is not None:
        m, plan = chosen.metrics, result.backtest.plan
        score = f"MASE {m.mase:.2f}, " if m.mase is not None else ""
        backtest = (
            f"{score}MAE {_num(m.mae)}, sMAPE {m.smape:.1f}% over {plan.n_windows} rolling windows "
            f"of {plan.backtest_horizon} steps"
        )
        rows.append(("Backtest", backtest))
    change = (
        ""
        if f.change_vs_prior is None
        else f" ({f.change_vs_prior:+.1%} vs the previous {f.horizon} periods, {_num(f.previous_total)})"
    )
    rows.append(("Sum of forecasts", f"{_num(f.total)}{change}"))
    rows.append(("Mean per period", _num(f.mean)))
    uncertainty = (
        f"80% interval {_num(f.first.lo_80)} to {_num(f.first.hi_80)} at {f.first.ds[:10]}, "
        f"{_num(f.last.lo_80)} to {_num(f.last.hi_80)} at {f.last.ds[:10]}"
    )
    rows.append(("Uncertainty", uncertainty))
    iv = result.intervals
    rows.append(("Intervals", f"{iv.method}; the model's own 80% interval covered {iv.native_coverage_80:.0%} of backtest actuals"
                              + (f", widened x{iv.factor_80:.2f}" if iv.method == "calibrated" else "")))  # fmt: skip
    width = max(len(k) for k, _ in rows)
    lines += [f"{k:<{width}}  {v}" for k, v in rows]
    shown = [w for w in result.warnings if w.severity == "warn"]
    if shown:
        lines += ["", "Warnings"] + [f"  [{w.code}] {w.message}" for w in shown]
    lines += ["", f"Files: {result.artifacts.directory}"]
    return "\n".join(lines)
