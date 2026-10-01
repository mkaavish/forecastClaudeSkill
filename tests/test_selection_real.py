"""Selection on real backtests of series whose true behaviour is known."""

import pytest

from forecast.backtest import plan_backtest, run_backtest
from forecast.loading import load_series
from forecast.models import context_from_profile, eligible_models
from forecast.profile import profile_series
from forecast.selection import select_model
from tests import synthetic

pytestmark = pytest.mark.slow
BASELINES = {"Naive", "SeasonalNaive", "HistoricAverage"}


def select(df, tmp_path, horizon=14):
    p = tmp_path / "d.csv"
    df.to_csv(p, index=False)
    loaded = load_series(p)
    profile = profile_series(loaded)
    ctx = context_from_profile(profile)
    plan = plan_backtest(ctx.n_obs, horizon, ctx.season_length)
    run, skipped = eligible_models(ctx)
    summary = run_backtest(loaded.data, loaded.freq, plan, run, skipped).summary
    return select_model(summary), summary


def test_white_noise_selects_a_baseline_across_seeds(tmp_path):
    for seed in range(6):
        sel, _ = select(synthetic.white_noise(seed=seed), tmp_path)
        assert sel.winner_kind == "baseline", (seed, sel.explanation)
        assert sel.winner in {"HistoricAverage", "Naive"}


def test_historic_average_is_the_baseline_for_noise(tmp_path):
    sel, _ = select(synthetic.white_noise(seed=1), tmp_path)
    assert sel.best_baseline == "HistoricAverage"


def test_seasonal_data_selects_a_seasonality_aware_model(tmp_path):
    for seed in range(4):
        sel, _ = select(synthetic.weekly_seasonality(seed=seed), tmp_path)
        assert sel.winner not in {"Naive", "HistoricAverage"}, sel.explanation
        assert sel.ranking[-1].name in {
            "HistoricAverage",
            "Naive",
        }  # the non-seasonal baselines rank last


def test_trend_plus_seasonality_selects_a_complex_model_by_a_wide_margin(tmp_path):
    for seed in range(4):
        sel, _ = select(synthetic.trend_seasonality(seed=seed), tmp_path)
        assert sel.winner_kind == "complex" and sel.reason == "beat_baseline_by_margin"
        assert sel.improvement_over_baseline > 0.5


def test_linear_trend_selects_a_complex_model(tmp_path):
    sel, _ = select(synthetic.linear_trend(), tmp_path)
    assert sel.winner_kind == "complex" and sel.improvement_over_baseline > 0.5


def test_random_walks_rarely_promote_a_complex_model(tmp_path):
    promoted = sum(
        select(synthetic.random_walk(seed=s), tmp_path)[0].winner_kind == "complex"
        for s in range(8)
    )
    assert promoted <= 2  # measured ~15% at the 5% margin (30% at 3%)


def test_zero_heavy_selects_among_baselines(tmp_path):
    sel, _ = select(synthetic.zero_heavy(), tmp_path)
    assert sel.reason == "only_baselines_ran" and sel.winner in BASELINES


def test_selection_is_reproducible(tmp_path):
    a, _ = select(synthetic.trend_seasonality(), tmp_path)
    b, _ = select(synthetic.trend_seasonality(), tmp_path)
    assert a.model_dump_json() == b.model_dump_json()
