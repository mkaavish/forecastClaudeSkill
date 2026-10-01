"""The forecast chart: history, where forecasting starts, the forecast, and its intervals.

Deliberately plain: one panel, two interval bands, no decoration. matplotlib is imported
lazily so the rest of the engine never pays for it.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from forecast.pipeline import Outcome

HISTORY_COLOR = "#334155"
FORECAST_COLOR = "#c2410c"
MUTED = "#6b7280"
MIN_HISTORY_POINTS = 90
MAX_AXIS_STRETCH = 1.6  # widest the axis may grow to show the 95% band
HISTORY_HORIZONS = 5  # show this many horizons of history, so the forecast stays legible


def plot_forecast(outcome: Outcome, path: str | Path) -> Path:
    import matplotlib

    matplotlib.use("Agg")  # no display needed; must precede the pyplot import
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    result, fc = outcome.result, outcome.forecast
    horizon = result.forecast.horizon
    history = outcome.history.tail(max(HISTORY_HORIZONS * horizon, MIN_HISTORY_POINTS)).copy()
    ds_hist, ds_fc = pd.DatetimeIndex(history["ds"]), pd.DatetimeIndex(fc["ds"])

    fig, ax = plt.subplots(figsize=(11, 5.6), dpi=150)
    ax.fill_between(
        ds_fc,
        fc["lo_95"],
        fc["hi_95"],
        color=FORECAST_COLOR,
        alpha=0.14,
        linewidth=0,
        label="95% interval",
    )
    ax.fill_between(
        ds_fc,
        fc["lo_80"],
        fc["hi_80"],
        color=FORECAST_COLOR,
        alpha=0.30,
        linewidth=0,
        label="80% interval",
    )
    ax.plot(ds_hist, history["y"], color=HISTORY_COLOR, linewidth=1.4, label="Observed")
    imputed = history["imputed"].to_numpy()
    if imputed.any():
        ax.scatter(ds_hist[imputed], history["y"][imputed], facecolors="white", edgecolors=HISTORY_COLOR,
                   s=22, zorder=3, label="Filled (missing)")  # fmt: skip
    # connect the last observation to the first forecast so the line is continuous
    ax.plot(pd.DatetimeIndex([ds_hist[-1], *ds_fc]), [history["y"].iloc[-1], *fc["forecast"]],
            color=FORECAST_COLOR, linewidth=1.8, label="Forecast")  # fmt: skip
    ax.axvline(ds_hist[-1], color=MUTED, linestyle="--", linewidth=1)
    ax.annotate("forecast starts", (ds_hist[-1], 1), xycoords=("data", "axes fraction"), xytext=(-5, -6),
                textcoords="offset points", ha="right", va="top", fontsize=9, color=MUTED)  # fmt: skip

    # Frame the history and the 80% band; include the 95% band too unless it would squash the rest.
    low = min(history["y"].min(), fc["lo_80"].min())
    high = max(history["y"].max(), fc["hi_80"].max())
    wide_low, wide_high = min(low, fc["lo_95"].min()), max(high, fc["hi_95"].max())
    if (wide_high - wide_low) <= MAX_AXIS_STRETCH * ((high - low) or 1.0):
        low, high = wide_low, wide_high
    pad = 0.06 * ((high - low) or 1.0)
    ax.set_ylim(low - pad, high + pad)
    clipped95 = bool((fc["hi_95"] > high + pad).any() or (fc["lo_95"] < low - pad).any())

    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(mdates.AutoDateLocator()))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.yaxis.set_major_formatter(
        FuncFormatter(lambda v, _: f"{v:,.0f}" if abs(v) >= 100 else f"{v:,.3g}")
    )
    ax.grid(axis="y", color="#e5e7eb", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    # above the axes, so it can never sit on top of the data
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False, ncols=4, fontsize=9)

    mase = _mase(result)
    fig.text(0.075, 0.955, f"{result.input.target_column}: {horizon}-period forecast", fontsize=14,
             fontweight="bold", color="#111827", ha="left")  # fmt: skip
    fig.text(0.075, 0.915, f"{result.forecast.model}{mase}  |  {result.input.frequency_name} data, "
             f"{result.input.n_obs} observations", fontsize=9.5, color=MUTED, ha="left")  # fmt: skip
    notes = _footnotes(result, clipped95)
    if notes:
        fig.text(0.075, 0.015, "  ".join(notes), fontsize=8.5, color=MUTED, ha="left")
    fig.subplots_adjust(left=0.075, right=0.975, top=0.84, bottom=0.12)

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, format="png", facecolor="white")
    plt.close(fig)
    return out


def _mase(result) -> str:
    chosen = next((m for m in result.backtest.models if m.name == result.forecast.model), None)
    if chosen is None or chosen.metrics is None or chosen.metrics.mase is None:
        return ""
    return f" (backtest MASE {chosen.metrics.mase:.2f}, {result.backtest.plan.n_windows} windows)"


def _footnotes(result, clipped95: bool) -> list[str]:
    notes = []
    if result.intervals.method == "calibrated":
        notes.append(
            f"Intervals widened x{result.intervals.factor_80:.2f} to match backtest coverage."
        )
    if clipped95:
        notes.append("95% band extends beyond the plotted range.")
    n_warn = sum(w.severity == "warn" for w in result.warnings)
    if n_warn:
        notes.append(f"{n_warn} warning{'s' if n_warn != 1 else ''}: see result.json.")
    return notes
