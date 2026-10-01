"""Every warning the engine can emit is catalogued, and every catalogued code has a trigger."""

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from forecast.backtest import plan_backtest, resolve_horizon
from forecast.diagnostics import WARNING_CODES, backtest_notices, series_notices
from forecast.loading import load_series
from forecast.profile import profile_series
from forecast.selection import select_model
from tests import synthetic
from tests.factories import model, summary

SRC = Path(__file__).resolve().parent.parent / "src" / "forecast"


def csv(tmp_path, df_or_text, name="d.csv"):
    p = tmp_path / name
    if isinstance(df_or_text, str):
        p.write_text(df_or_text)
    else:
        df_or_text.to_csv(p, index=False)
    return p


def load_codes(tmp_path, df_or_text, **kw):
    return {n.code for n in load_series(csv(tmp_path, df_or_text), **kw).report.notices}


def profile_codes(tmp_path, df):
    return {w.code for w in profile_series(load_series(csv(tmp_path, df))).warnings}


def backtest_codes(*models):
    s = summary(*models)
    prof = None

    class _P:  # only the stats the notices read
        class stats:
            q25, q75 = 0.0, 1.0

    prof = _P()
    return {n.code for n in backtest_notices(s, select_model(s), prof)}


def daily(n=40, **cols):
    return pd.DataFrame({"date": pd.date_range("2024-01-01", periods=n), **cols})


def weekly_plus_annual():
    rng = np.random.default_rng(4)
    t = np.arange(3 * 365)
    y = (
        100
        + 8 * np.sin(2 * np.pi * t / 7)
        + 15 * np.sin(2 * np.pi * t / 365)
        + rng.normal(0, 1, len(t))
    )
    return pd.DataFrame({"date": pd.date_range("2021-01-01", periods=len(t)), "value": y})


def _short_history(tmp_path):
    return {
        n.code
        for n in series_notices(
            profile_series(load_series(csv(tmp_path, synthetic.linear_trend(30))))
        )
    }


def _near_constant(tmp_path):
    df = synthetic.constant(100, level=7.0)
    df.loc[[10, 50], "value"] = 8.0
    return profile_codes(tmp_path, df)


def _outliers(tmp_path):
    df = synthetic.weekly_seasonality(210)
    df.loc[[30, 100], "value"] += 200
    return profile_codes(tmp_path, df)


def _unbalanced(tmp_path):
    rows = [
        {"date": d, "store": s, "sales": 10}
        for d in pd.date_range("2024-01-01", periods=30)
        for s in "AB"
        if not (s == "B" and d.day == 15)
    ]
    return load_codes(tmp_path, pd.DataFrame(rows), agg="sum")


def _off_calendar(tmp_path):
    text = (
        "date,sales\n"
        + "\n".join(f"2024-01-{d:02d},{d}" for d in range(1, 31))
        + "\n2024-01-10 12:00,5\n"
    )
    return load_codes(tmp_path, text)


def _date_rows_dropped(tmp_path):
    rows = [f"2024-01-{d:02d},{d}" for d in range(1, 31)]
    rows.insert(5, "not-a-date,3")
    return load_codes(tmp_path, "date,sales\n" + "\n".join(rows))


TRIGGERS = {
    # loading
    "TARGET_AUTO_SELECTED": lambda t: load_codes(t, daily(units_sold=range(40), price=[9.9] * 40)),
    "INVALID_VALUES": lambda t: load_codes(
        t,
        "date,sales\n" + "\n".join(f"2024-01-{d:02d},{'x' if d == 9 else d}" for d in range(1, 31)),
    ),
    "DATE_ROWS_DROPPED": _date_rows_dropped,
    "DUPLICATE_ROWS_DROPPED": lambda t: load_codes(
        t, pd.concat([daily(value=range(40)), daily(value=range(40)).head(2)])
    ),
    "UNBALANCED_PANEL": _unbalanced,
    "OFF_CALENDAR_DROPPED": _off_calendar,
    "EDGES_TRIMMED": lambda t: load_codes(
        t, synthetic.with_missing_values(synthetic.linear_trend(60), [0, 59])
    ),
    "MISSING_FILLED": lambda t: load_codes(
        t, synthetic.with_missing_values(synthetic.linear_trend(60), [20])
    ),
    # profiling
    "CONSTANT_SERIES": lambda t: profile_codes(t, synthetic.constant()),
    "NEAR_CONSTANT": _near_constant,
    "INTERMITTENT": lambda t: profile_codes(t, synthetic.zero_heavy()),
    "NEGATIVE_VALUES": lambda t: profile_codes(t, synthetic.white_noise(level=0.0)),
    "OUTLIERS": _outliers,
    "SEASONALITY_UNTESTED": lambda t: profile_codes(t, synthetic.linear_trend(10)),
    "NO_SEASONALITY": lambda t: profile_codes(t, synthetic.white_noise()),
    "MULTIPLE_SEASONALITY": lambda t: profile_codes(t, weekly_plus_annual()),
    "SHORT_HISTORY": _short_history,
    # planning
    "HORIZON_DEFAULT_REDUCED": lambda t: {n.code for n in resolve_horizon(None, "MS", 48, 12)[1]},
    "BACKTEST_HORIZON_SHORTENED": lambda t: {n.code for n in plan_backtest(60, 14, 7).notices},
    "HORIZON_LONG": lambda t: {n.code for n in plan_backtest(200, 50, 7).notices},
    "FEW_BACKTEST_WINDOWS": lambda t: {n.code for n in plan_backtest(24 + 3 * 28, 28, 7).notices},
    # backtest
    "MODEL_FAILED": lambda t: backtest_codes(
        model("Naive", 1.0), model("AutoARIMA", status="failed", reason="x")
    ),
    "MODEL_ADJUSTED": lambda t: backtest_codes(
        model("Naive", 1.0), model("AutoETS", 0.4, reason="adjusted")
    ),
    "BASELINE_WON": lambda t: backtest_codes(model("Naive", 1.0), model("AutoETS", 1.4)),
    "POOR_BACKTEST": lambda t: backtest_codes(model("Naive", 1.6), model("AutoETS", 1.2)),
    "UNSTABLE_ACROSS_WINDOWS": lambda t: backtest_codes(
        model("Naive", 2.0), model("AutoETS", 0.5, window_mae=[0.2, 0.3, 3.0, 0.25, 0.3])
    ),
    "RECENT_DEGRADATION": lambda t: backtest_codes(
        model("Naive", 2.0), model("AutoETS", 0.5, window_mae=[1.0, 1.0, 1.1, 0.9, 2.4])
    ),
    "LOW_COVERAGE": lambda t: backtest_codes(
        model("Naive", 2.0), model("AutoETS", 0.5, coverage_80=0.4)
    ),
    "WIDE_INTERVALS": lambda t: backtest_codes(
        model("Naive", 2.0), model("AutoETS", 0.5, width=5.0)
    ),
}


def test_every_catalogued_code_has_a_trigger_that_fires(tmp_path):
    assert set(TRIGGERS) == set(WARNING_CODES), "catalogue and triggers must list the same codes"
    for code, trigger in TRIGGERS.items():
        assert code in trigger(tmp_path), f"{code} did not fire"


def test_no_source_file_emits_an_uncatalogued_code():
    emitted = set()
    for path in SRC.glob("*.py"):
        emitted |= set(re.findall(r'code="([A-Z_]+)"', path.read_text()))
    assert emitted - set(WARNING_CODES) == set(), "emitted but not in WARNING_CODES"
    assert set(WARNING_CODES) - emitted == set(), "catalogued but never emitted"


@pytest.mark.parametrize("code", sorted(WARNING_CODES))
def test_each_code_has_a_description(code):
    assert WARNING_CODES[code].endswith(".") and len(WARNING_CODES[code]) > 20
