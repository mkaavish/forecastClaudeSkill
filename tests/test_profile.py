import numpy as np
import pandas as pd
import pytest

from forecast.loading import load_series
from forecast.profile import profile_series
from forecast.schema import ProfileReport
from tests import synthetic


def profile(tmp_path, df, name="data.csv", **kw):
    p = tmp_path / name
    df.to_csv(p, index=False)
    return profile_series(load_series(p, **kw))


def codes(report):
    return {w.code for w in report.warnings}


# ------------------------------------------------------------ seasonality


def test_weekly_seasonality_detected(tmp_path):
    r = profile(tmp_path, synthetic.weekly_seasonality())
    assert r.seasonality.season_length == 7 and not r.seasonality.multiple
    cand = next(c for c in r.seasonality.candidates if c.period == 7)
    assert cand.detected and cand.strength > 0.9 and cand.p_value < 1e-10


def test_annual_candidate_skipped_without_two_cycles(tmp_path):
    r = profile(tmp_path, synthetic.weekly_seasonality(300))
    c365 = next(c for c in r.seasonality.candidates if c.period == 365)
    assert not c365.tested and "fewer than 2 full cycles" in c365.note


def test_white_noise_has_no_seasonality_across_seeds(tmp_path):
    for seed in range(15):
        r = profile(tmp_path, synthetic.white_noise(seed=seed))
        assert r.seasonality.season_length == 1, seed
    assert "NO_SEASONALITY" in codes(r)


def test_random_walk_and_trend_are_not_seasonal(tmp_path):
    for df in (synthetic.random_walk(), synthetic.linear_trend(), synthetic.level_shift()):
        assert profile(tmp_path, df).seasonality.season_length == 1


def test_weak_but_real_seasonality_detected(tmp_path):
    hits = sum(
        profile(
            tmp_path, synthetic.weekly_seasonality(amplitude=3.0, noise=5.0, seed=s)
        ).seasonality.season_length
        == 7
        for s in range(10)
    )
    assert hits >= 9


def test_monthly_seasonality_period_12(tmp_path):
    rng = np.random.default_rng(1)
    t = np.arange(48)
    y = 100 + 0.5 * t + 12 * np.sin(2 * np.pi * t / 12) + rng.normal(0, 1.5, 48)
    df = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=48, freq="MS"), "value": y})
    r = profile(tmp_path, df)
    assert r.input.frequency == "MS" and r.seasonality.season_length == 12


def test_hourly_daily_pattern_is_not_reported_as_multiple(tmp_path):
    rng = np.random.default_rng(2)
    t = np.arange(24 * 7 * 8)
    y = 50 + 10 * np.sin(2 * np.pi * t / 24) + rng.normal(0, 1, len(t))
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=len(t), freq="h"), "value": y})
    r = profile(tmp_path, df)
    assert r.seasonality.season_length == 24 and not r.seasonality.multiple


def test_hourly_daily_plus_weekly_is_multiple(tmp_path):
    rng = np.random.default_rng(3)
    idx = pd.date_range("2024-01-01", periods=24 * 7 * 8, freq="h")
    y = (
        50
        + 10 * np.sin(2 * np.pi * np.arange(len(idx)) / 24)
        - 12 * (idx.dayofweek >= 5)
        + rng.normal(0, 1, len(idx))
    )
    r = profile(tmp_path, pd.DataFrame({"date": idx, "value": y}))
    assert r.seasonality.multiple and "MULTIPLE_SEASONALITY" in codes(r)
    assert {c.period for c in r.seasonality.candidates if c.detected} == {24, 168}


def test_daily_weekly_plus_annual_is_multiple(tmp_path):
    rng = np.random.default_rng(4)
    t = np.arange(3 * 365)
    y = (
        100
        + 8 * np.sin(2 * np.pi * t / 7)
        + 15 * np.sin(2 * np.pi * t / 365)
        + rng.normal(0, 1, len(t))
    )
    r = profile(
        tmp_path, pd.DataFrame({"date": pd.date_range("2021-01-01", periods=len(t)), "value": y})
    )
    assert r.seasonality.multiple
    assert {c.period for c in r.seasonality.candidates if c.detected} == {7, 365}


# ------------------------------------------------------------ trend


def test_linear_trend_slope_recovered(tmp_path):
    r = profile(tmp_path, synthetic.linear_trend(slope=2.0))
    assert r.trend.direction == "positive"
    assert r.trend.slope_per_period == pytest.approx(2.0, abs=0.05)


def test_negative_trend(tmp_path):
    assert (
        profile(tmp_path, synthetic.linear_trend(slope=-1.0, intercept=500)).trend.direction
        == "negative"
    )


def test_white_noise_has_no_trend_across_seeds(tmp_path):
    assert all(
        profile(tmp_path, synthetic.white_noise(seed=s)).trend.direction == "none"
        for s in range(15)
    )


def test_trend_with_seasonality_still_found(tmp_path):
    r = profile(tmp_path, synthetic.trend_seasonality())
    assert r.trend.direction == "positive" and r.trend.slope_per_period == pytest.approx(
        0.5, abs=0.05
    )
    assert r.seasonality.season_length == 7 and r.seasonality.trend_strength > 0.9


# ------------------------------------------------------------ constant / intermittent / negative


def test_constant_series(tmp_path):
    r = profile(tmp_path, synthetic.constant())
    assert r.constant and "CONSTANT_SERIES" in codes(r)
    assert (
        r.seasonality.season_length == 1
        and r.trend.direction == "none"
        and r.outliers.n_outliers == 0
    )
    assert all(not c.tested for c in r.seasonality.candidates)


def test_near_constant_series(tmp_path):
    df = synthetic.constant(100, level=7.0)
    df.loc[[10, 50], "value"] = 8.0
    r = profile(tmp_path, df)
    assert not r.constant and r.near_constant and "NEAR_CONSTANT" in codes(r)


def test_zero_heavy_demand_is_flagged_intermittent(tmp_path):
    r = profile(tmp_path, synthetic.zero_heavy())
    assert r.intermittency.zero_heavy and r.intermittency.demand_class in ("intermittent", "lumpy")
    assert r.stats.zero_fraction == pytest.approx(0.7, abs=0.1) and "INTERMITTENT" in codes(r)


def test_smooth_demand_not_intermittent(tmp_path):
    r = profile(tmp_path, synthetic.weekly_seasonality())
    assert not r.intermittency.zero_heavy and r.intermittency.demand_class == "smooth"


def test_negative_values_noted_and_intermittency_not_applicable(tmp_path):
    df = synthetic.white_noise(level=0.0, noise=5.0)
    r = profile(tmp_path, df)
    assert (
        r.stats.n_negative > 0 and "NEGATIVE_VALUES" in codes(r) and not r.intermittency.applicable
    )


# ------------------------------------------------------------ outliers


def test_outliers_flagged_at_injected_positions_and_kept(tmp_path):
    df = synthetic.weekly_seasonality(210)
    positions = [30, 100, 170]
    df.loc[positions, "value"] += [150, -150, 150]
    r = profile(tmp_path, df)
    flagged = {pd.Timestamp(o.ds) for o in r.outliers.top}
    assert {df["date"].iloc[i] for i in positions} <= flagged
    assert r.input.n_obs == 210  # nothing removed


def test_clean_series_has_almost_no_outliers(tmp_path):
    for df in (synthetic.trend_seasonality(), synthetic.linear_trend(), synthetic.white_noise()):
        assert profile(tmp_path, df).outliers.fraction <= 0.01


# ------------------------------------------------------------ misc


def test_short_series_degrades_gracefully(tmp_path):
    r = profile(tmp_path, synthetic.linear_trend(10))
    assert all(not c.tested for c in r.seasonality.candidates) and "SEASONALITY_UNTESTED" in codes(
        r
    )
    r6 = profile(tmp_path, synthetic.linear_trend(6))
    assert r6.trend.direction == "insufficient_data"


def test_profile_carries_load_facts_and_missing_data(tmp_path):
    df = synthetic.with_missing_values(synthetic.weekly_seasonality(), [20, 21])
    r = profile(tmp_path, df)
    assert r.input.n_missing_values == 2 and r.input.n_imputed == 2 and r.input.frequency == "D"


def test_profile_is_deterministic_and_schema_valid(tmp_path):
    a = profile(tmp_path, synthetic.trend_seasonality())
    b = profile(tmp_path, synthetic.trend_seasonality())
    assert a.model_dump_json() == b.model_dump_json()
    assert ProfileReport.model_validate_json(a.model_dump_json()) == a


def test_random_walks_are_not_called_trending(tmp_path):
    flagged = sum(
        profile(tmp_path, synthetic.random_walk(seed=s)).trend.direction != "none"
        for s in range(40)
    )
    assert flagged <= 3  # ~1% expected; Kendall alone gave 30/40


def test_trend_found_in_noisy_seasonal_series_across_seeds(tmp_path):
    for seed in range(8):
        r = profile(tmp_path, synthetic.trend_seasonality(seed=seed))
        assert r.trend.direction == "positive", seed


def test_noisy_trend_with_small_per_step_growth_is_still_found(tmp_path):
    # growth of 730 over the span but noise 30 per step: differencing alone cannot see it
    for seed in range(5):
        r = profile(tmp_path, synthetic.linear_trend(n=730, slope=1.0, noise=30.0, seed=seed))
        assert r.trend.direction == "positive", seed
        assert (
            r.trend.drift_p_value > 0.01 and r.trend.adf_p_value < 0.01
        )  # found via the ADF guard


def test_noisy_seasonal_trend_found_in_the_retail_example():
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "examples" / "retail_sales.csv"
    r = profile_series(load_series(path))
    assert r.trend.direction == "positive" and r.seasonality.season_length == 7
