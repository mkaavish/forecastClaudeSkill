"""End-to-end honesty checks: warnings appear when the data warrants them, and not otherwise."""

import pytest

from forecast.backtest import plan_backtest, run_backtest
from forecast.diagnostics import backtest_notices
from forecast.loading import load_series
from forecast.models import context_from_profile, eligible_models
from forecast.profile import profile_series
from forecast.selection import select_model
from tests import synthetic

pytestmark = pytest.mark.slow


def warning_codes(df, tmp_path, horizon=14):
    p = tmp_path / "d.csv"
    df.to_csv(p, index=False)
    loaded = load_series(p)
    profile = profile_series(loaded)
    ctx = context_from_profile(profile)
    plan = plan_backtest(ctx.n_obs, horizon, ctx.season_length)
    run, skipped = eligible_models(ctx)
    summary = run_backtest(loaded.data, loaded.freq, plan, run, skipped).summary
    return {n.code for n in backtest_notices(summary, select_model(summary), profile)}


def test_clean_predictable_series_raises_no_warnings(tmp_path):
    for seed in range(3):
        assert warning_codes(synthetic.trend_seasonality(seed=seed), tmp_path) == set()


def test_white_noise_notes_the_baseline_choice_and_rarely_anything_else(tmp_path):
    results = [warning_codes(synthetic.white_noise(seed=seed), tmp_path) for seed in range(6)]
    assert all("BASELINE_WON" in codes for codes in results)
    assert all(codes <= {"BASELINE_WON", "POOR_BACKTEST"} for codes in results)
    # the mean beats Naive by ~30% on noise, so "barely better than Naive" is a rare flag
    assert sum("POOR_BACKTEST" in codes for codes in results) <= 2


def test_random_walk_is_flagged_as_poorly_predictable(tmp_path):
    for seed in range(3):
        assert "POOR_BACKTEST" in warning_codes(synthetic.random_walk(seed=seed), tmp_path)


def test_late_structural_break_is_flagged_by_several_warnings(tmp_path):
    for seed in range(3):
        df = synthetic.level_shift(n=200, shift_at=190, shift=60, seed=seed)
        codes = warning_codes(df, tmp_path)
        assert {"RECENT_DEGRADATION", "POOR_BACKTEST", "UNSTABLE_ACROSS_WINDOWS"} <= codes, (
            seed,
            codes,
        )
