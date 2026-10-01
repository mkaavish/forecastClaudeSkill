"""Backtest-based warnings: each fires on the condition it describes and stays quiet otherwise."""

import pytest

from forecast.diagnostics import backtest_notices, series_notices
from forecast.loading import load_series
from forecast.profile import profile_series
from forecast.selection import select_model
from tests import synthetic
from tests.factories import model, summary


@pytest.fixture(scope="module")
def profile(tmp_path_factory):
    p = tmp_path_factory.mktemp("prof") / "d.csv"
    synthetic.white_noise(n=300).to_csv(p, index=False)
    return profile_series(load_series(p))


def notices(profile, *models, **kw):
    s = summary(*models, **kw)
    return backtest_notices(s, select_model(s), profile)


def codes(profile, *models, **kw):
    return {n.code for n in notices(profile, *models, **kw)}


HEALTHY = (model("Naive", 1.0), model("SeasonalNaive", 0.8), model("AutoETS", 0.5, season_length=7))


def test_healthy_complex_winner_raises_no_warnings(profile):
    assert notices(profile, *HEALTHY) == []


def test_model_failed_names_the_model_and_reason(profile):
    out = notices(
        profile, *HEALTHY, model("AutoARIMA", status="failed", reason="RuntimeError: boom")
    )
    (n,) = [n for n in out if n.code == "MODEL_FAILED"]
    assert n.severity == "warn" and "AutoARIMA" in n.message and "boom" in n.message


def test_model_adjusted_when_winner_config_was_changed(profile):
    adjusted = model(
        "AutoARIMA", 0.4, reason="period 168 is too long for AutoARIMA; fitted without seasonality"
    )
    out = notices(profile, model("Naive", 1.0), adjusted)
    assert [n.code for n in out] == ["MODEL_ADJUSTED"] and out[0].severity == "info"


def test_baseline_won_only_when_a_complex_model_actually_ran(profile):
    assert "BASELINE_WON" in codes(profile, model("Naive", 1.0), model("AutoETS", 1.3))
    assert "BASELINE_WON" in codes(
        profile, model("Naive", 1.0), model("AutoETS", 0.98)
    )  # within margin
    assert "BASELINE_WON" not in codes(
        profile, model("Naive", 1.0), model("AutoETS", status="skipped")
    )
    assert "BASELINE_WON" not in codes(profile, *HEALTHY)


def test_poor_backtest_when_winner_mase_reaches_one(profile):
    assert "POOR_BACKTEST" in codes(profile, model("Naive", 1.6), model("AutoETS", 1.2))
    assert "POOR_BACKTEST" not in codes(profile, model("Naive", 1.6), model("AutoETS", 0.99))


def test_poor_backtest_is_skipped_when_mase_is_undefined(profile):
    s = summary(model("Naive", None), model("AutoETS", None), scale=None)
    assert "POOR_BACKTEST" not in {n.code for n in backtest_notices(s, select_model(s), profile)}


def test_unstable_when_window_errors_vary_wildly(profile):
    spiky = model("AutoETS", 0.5, window_mae=[0.2, 0.3, 3.0, 0.25, 0.3])
    assert "UNSTABLE_ACROSS_WINDOWS" in codes(profile, model("Naive", 2.0), spiky)


def test_unstable_when_complex_winner_rarely_beats_the_baseline_window_by_window(profile):
    base = model("Naive", 1.0, window_mae=[2.0, 2.0, 2.0, 2.0, 2.0])
    # better on average (one huge win) but loses 4 of 5 windows
    complex_ = model("AutoETS", 0.7, window_mae=[2.4, 2.4, 2.4, 2.4, 0.5])
    out = {n.code: n for n in notices(profile, base, complex_)}
    assert "beat the baseline in only 1 of 5 windows" in out["UNSTABLE_ACROSS_WINDOWS"].message


def test_stable_windows_are_not_flagged(profile):
    steady = model("AutoETS", 0.5, window_mae=[1.0, 1.1, 0.9, 1.0, 1.05])
    assert "UNSTABLE_ACROSS_WINDOWS" not in codes(profile, model("Naive", 2.0), steady)


def test_recent_degradation_when_the_last_window_blows_up(profile):
    worse = model("AutoETS", 0.5, window_mae=[1.0, 1.0, 1.1, 0.9, 2.4])
    assert "RECENT_DEGRADATION" in codes(profile, model("Naive", 2.0), worse)
    ok = model("AutoETS", 0.5, window_mae=[1.0, 1.0, 1.1, 0.9, 1.3])
    assert "RECENT_DEGRADATION" not in codes(profile, model("Naive", 2.0), ok)


def test_low_coverage_when_the_80_interval_misses_too_much(profile):
    low = model("SeasonalNaive", 0.5, coverage_80=0.47)
    assert "LOW_COVERAGE" in codes(profile, model("Naive", 2.0), low)
    assert "LOW_COVERAGE" not in codes(
        profile, model("Naive", 2.0), model("SeasonalNaive", 0.5, coverage_80=0.7)
    )


def test_wide_intervals_relative_to_the_history_spread(profile):
    iqr = profile.stats.q75 - profile.stats.q25
    wide = model("AutoETS", 0.5, width=3.5 * iqr)
    narrow = model("AutoETS", 0.5, width=2.0 * iqr)
    assert "WIDE_INTERVALS" in codes(profile, model("Naive", 2.0), wide)
    assert "WIDE_INTERVALS" not in codes(profile, model("Naive", 2.0), narrow)


def test_notice_details_are_json_friendly(profile):
    out = notices(
        profile,
        model("Naive", 3.0),
        model("AutoETS", 1.2, coverage_80=0.3, window_mae=[1, 1, 1, 1, 9]),
        model("AutoARIMA", status="failed", reason="x"),
    )
    assert len(out) >= 4
    for n in out:
        n.model_dump_json()


# ------------------------------------------------------------ series-level


def series_codes(tmp_path, df):
    p = tmp_path / "d.csv"
    df.to_csv(p, index=False)
    return [n.code for n in series_notices(profile_series(load_series(p)))]


def test_short_history_flagged_by_observation_count(tmp_path):
    assert series_codes(tmp_path, synthetic.linear_trend(30)) == ["SHORT_HISTORY"]
    assert series_codes(tmp_path, synthetic.linear_trend(120)) == []


def test_short_history_flagged_by_seasonal_cycles(tmp_path):
    import numpy as np
    import pandas as pd

    t = np.arange(60)
    df = pd.DataFrame({
        "date": pd.date_range("2000-01-01", periods=60, freq="YS"),
        "value": 100 + t,
    })  # fmt: skip
    assert series_codes(tmp_path, df) == []  # yearly: no season, 60 obs
    long_season = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=2 * 24 * 3 + 4, freq="h"),
            "value": 50
            + 10 * np.sin(2 * np.pi * np.arange(2 * 24 * 3 + 4) / 24)
            + np.random.default_rng(0).normal(0, 1, 2 * 24 * 3 + 4),
        }
    )  # 76 obs, 3.2 daily cycles -> ok on count and cycles
    assert series_codes(tmp_path, long_season) == []
    two_cycles = long_season.head(24 * 2 + 4)  # 52 obs but ~2 cycles: SHORT_HISTORY via cycles
    assert series_codes(tmp_path, two_cycles) == ["SHORT_HISTORY"]
