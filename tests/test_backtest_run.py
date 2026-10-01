import json

import numpy as np
import pandas as pd
import pytest

from forecast import models as models_module
from forecast.backtest import FRAME_COLUMNS, plan_backtest, run_backtest
from forecast.diagnostics import check_forecastable
from forecast.loading import load_series
from forecast.models import REGISTRY, Eligibility, context_from_profile, eligible_models
from forecast.outputs import write_backtest_csv
from forecast.profile import profile_series
from forecast.schema import BacktestSummary
from tests import synthetic

pytestmark = pytest.mark.slow
SPEC = {s.name: s for s in REGISTRY}


def backtest(df, horizon, tmp_path, name="d.csv"):
    p = tmp_path / name
    df.to_csv(p, index=False)
    loaded = load_series(p)
    profile = profile_series(loaded)
    check_forecastable(profile)
    ctx = context_from_profile(profile)
    plan = plan_backtest(ctx.n_obs, horizon, ctx.season_length)
    run, skipped = eligible_models(ctx)
    return loaded, plan, run_backtest(loaded.data, loaded.freq, plan, run, skipped)


def by_name(result):
    return {m.name: m for m in result.summary.models}


@pytest.fixture(scope="module")
def seasonal(tmp_path_factory):
    return backtest(synthetic.trend_seasonality(400), 28, tmp_path_factory.mktemp("seasonal"))


# ------------------------------------------------------------ structure and alignment


def test_all_models_run_and_frame_matches_contract(seasonal):
    _, plan, result = seasonal
    assert {m.name for m in result.summary.models if m.status == "ok"} == set(SPEC)
    assert list(result.frame.columns) == FRAME_COLUMNS
    assert len(result.frame) == len(SPEC) * plan.n_windows * plan.backtest_horizon
    assert set(result.frame["step"]) == set(range(1, plan.backtest_horizon + 1))


def test_windows_align_with_the_plan_and_actuals_match_data(seasonal):
    loaded, plan, result = seasonal
    data = loaded.data.set_index("ds")["y"]
    naive = result.frame[result.frame["model"] == "Naive"]
    for w in plan.windows:
        rows = naive[naive["window"] == w.index]
        assert pd.Timestamp(rows["cutoff"].iloc[0]) == loaded.data["ds"].iloc[w.train_end - 1]
        assert list(rows["ds"]) == list(loaded.data["ds"].iloc[w.test_start : w.test_end])
        np.testing.assert_allclose(rows["y"].to_numpy(), data.loc[rows["ds"]].to_numpy())
        assert (rows["ds"] > rows["cutoff"]).all()  # every forecast is strictly out of sample


def test_naive_forecast_is_last_training_value_so_no_leakage(seasonal):
    loaded, plan, result = seasonal
    naive = result.frame[result.frame["model"] == "Naive"]
    for w in plan.windows:
        last_train = loaded.data["y"].iloc[w.train_end - 1]
        assert np.allclose(naive[naive["window"] == w.index]["yhat"], last_train)


def test_intervals_bracket_forecasts_and_nest(seasonal):
    _, _, result = seasonal
    f = result.frame
    assert (f["lo_80"] <= f["yhat"]).all() and (f["yhat"] <= f["hi_80"]).all()
    assert (f["lo_95"] <= f["lo_80"]).all() and (f["hi_80"] <= f["hi_95"]).all()


def test_pooled_metrics_match_the_frame(seasonal):
    _, plan, result = seasonal
    summary = result.summary
    for m in summary.models:
        rows = result.frame[result.frame["model"] == m.name]
        assert m.metrics.mae == pytest.approx(np.mean(np.abs(rows["y"] - rows["yhat"])))
        assert m.metrics.mase == pytest.approx(m.metrics.mae / summary.mase_scale)
        assert len(m.metrics.window_mae) == plan.n_windows
        assert np.mean(m.metrics.window_mae) == pytest.approx(m.metrics.mae)  # equal-sized windows
    assert summary.mase_scale_source == "initial_training"


def test_summary_validates_and_is_json_serialisable(seasonal):
    _, _, result = seasonal
    text = result.summary.model_dump_json()
    assert BacktestSummary.model_validate_json(text) == result.summary
    json.loads(text)


def test_backtest_csv_round_trip(seasonal, tmp_path):
    _, _, result = seasonal
    path = write_backtest_csv(result.frame, tmp_path / "out" / "backtest.csv")
    back = pd.read_csv(path)
    assert list(back.columns) == FRAME_COLUMNS and len(back) == len(result.frame)
    assert back["ds"].iloc[0].startswith("20") and "T00:00:00" in back["ds"].iloc[0]
    np.testing.assert_allclose(back["yhat"], result.frame["yhat"])


def test_backtest_is_deterministic(seasonal, tmp_path):
    loaded, plan, result = seasonal
    ctx = context_from_profile(profile_series(loaded))
    run, skipped = eligible_models(ctx)
    again = run_backtest(loaded.data, loaded.freq, plan, run, skipped)
    pd.testing.assert_frame_equal(result.frame, again.frame)


# ------------------------------------------------------------ known-truth behaviour


def test_trend_plus_seasonality_ranking(seasonal):
    m = {name: r.metrics for name, r in by_name(seasonal[2]).items()}
    assert m["AutoETS"].mase < m["SeasonalNaive"].mase < m["Naive"].mase
    assert m["AutoARIMA"].mase < m["Naive"].mase and m["AutoTheta"].mase < m["Naive"].mase
    assert m["HistoricAverage"].mase > m["Naive"].mase  # the mean is hopeless under a trend


def test_ets_interval_coverage_is_near_nominal_on_clean_data(seasonal):
    cov = by_name(seasonal[2])["AutoETS"].metrics
    assert 0.6 <= cov.coverage_80 <= 0.95 and cov.coverage_95 >= 0.85


def test_pure_seasonality_makes_seasonal_naive_far_better_than_naive(tmp_path):
    _, _, result = backtest(synthetic.weekly_seasonality(), 14, tmp_path)
    m = {name: r.metrics for name, r in by_name(result).items()}
    assert m["Naive"].mase > 3 * m["SeasonalNaive"].mase


def test_white_noise_historic_average_beats_naive(tmp_path):
    _, _, result = backtest(synthetic.white_noise(), 14, tmp_path)
    m = {name: r.metrics for name, r in by_name(result).items()}
    assert m["HistoricAverage"].mae < m["Naive"].mae
    assert "SeasonalNaive" in {x.name for x in result.summary.models if x.status == "skipped"}


def test_random_walk_naive_beats_historic_average(tmp_path):
    _, _, result = backtest(synthetic.random_walk(), 14, tmp_path)
    m = {name: r.metrics for name, r in by_name(result).items()}
    assert m["Naive"].mae < m["HistoricAverage"].mae


def test_zero_heavy_series_runs_baselines_and_records_skips(tmp_path):
    _, _, result = backtest(synthetic.zero_heavy(), 14, tmp_path)
    states = {m.name: m.status for m in result.summary.models}
    assert states["Naive"] == "ok" and states["HistoricAverage"] == "ok"
    assert states["AutoETS"] == states["AutoARIMA"] == states["AutoTheta"] == "skipped"
    complex_skips = [
        m for m in result.summary.models if m.status == "skipped" and m.kind == "complex"
    ]
    assert len(complex_skips) == 3 and all("intermittent" in m.reason for m in complex_skips)


def test_models_survive_negative_values(tmp_path):
    _, _, result = backtest(synthetic.white_noise(level=0.0, noise=5.0), 14, tmp_path)
    assert all(m.status == "ok" for m in result.summary.models if m.name != "SeasonalNaive")


def test_monthly_series_with_period_12(tmp_path):
    rng = np.random.default_rng(1)
    t = np.arange(96)
    df = pd.DataFrame({
        "date": pd.date_range("2016-01-01", periods=96, freq="MS"),
        "value": 100 + 0.5 * t + 12 * np.sin(2 * np.pi * t / 12) + rng.normal(0, 1.5, 96),
    })  # fmt: skip
    loaded, plan, result = backtest(df, 12, tmp_path)
    assert loaded.freq == "MS" and plan.season_length == 12
    assert all(m.status == "ok" for m in result.summary.models)
    assert by_name(result)["SeasonalNaive"].metrics.mase < by_name(result)["Naive"].metrics.mase


# ------------------------------------------------------------ failure isolation


class _Boom:
    """Stands in for a model whose fit raises."""

    def __init__(self, alias):
        self.alias = alias

    def __getattr__(self, name):
        raise RuntimeError("synthetic fitting failure")


def _patched_builder(monkeypatch, victim, factory):
    real = models_module.build_model

    def build(spec, season_length):
        return factory(spec) if spec.name == victim else real(spec, season_length)

    monkeypatch.setattr("forecast.backtest.build_model", build)


def test_one_model_failing_does_not_stop_the_others(monkeypatch, tmp_path):
    _patched_builder(monkeypatch, "AutoARIMA", lambda spec: _Boom(spec.name))
    _, _, result = backtest(synthetic.trend_seasonality(300), 14, tmp_path)
    by = by_name(result)
    assert (
        by["AutoARIMA"].status == "failed" and "synthetic fitting failure" in by["AutoARIMA"].reason
    )
    assert by["AutoARIMA"].metrics is None
    assert all(by[n].status == "ok" for n in SPEC if n != "AutoARIMA")
    assert "AutoARIMA" not in set(result.frame["model"])


def test_nonfinite_forecasts_are_a_failure(monkeypatch, tmp_path):
    from statsforecast.models import Naive

    class NanNaive(Naive):
        def forecast(self, y, h, X=None, X_future=None, level=None, fitted=False):
            out = super().forecast(y, h, X, X_future, level, fitted)
            out["mean"] = out["mean"] * np.nan
            return out

    _patched_builder(monkeypatch, "AutoTheta", lambda spec: NanNaive(alias=spec.name))
    _, _, result = backtest(synthetic.trend_seasonality(300), 14, tmp_path)
    assert by_name(result)["AutoTheta"].status == "failed"
    assert "non-finite" in by_name(result)["AutoTheta"].reason
    assert by_name(result)["AutoETS"].status == "ok"


def test_model_without_interval_columns_is_a_failure_not_a_crash(monkeypatch, tmp_path):
    from statsforecast.models import Naive

    class NoIntervals(Naive):
        def forecast(self, y, h, X=None, X_future=None, level=None, fitted=False):
            return super().forecast(y, h, X, X_future, None, fitted)  # drops the intervals

    _patched_builder(monkeypatch, "AutoTheta", lambda spec: NoIntervals(alias=spec.name))
    _, _, result = backtest(synthetic.trend_seasonality(300), 14, tmp_path)
    theta = by_name(result)["AutoTheta"]
    assert theta.status == "failed" and theta.metrics is None
    assert by_name(result)["AutoETS"].status == "ok"


def test_all_models_failing_returns_empty_frame_not_a_crash(monkeypatch, tmp_path):
    monkeypatch.setattr("forecast.backtest.build_model", lambda spec, m: _Boom(spec.name))
    _, _, result = backtest(synthetic.trend_seasonality(300), 14, tmp_path)
    assert result.frame.empty and all(
        m.status == "failed" for m in result.summary.models if m.status != "skipped"
    )


# ------------------------------------------------------------ MASE scale fallback


def test_flat_initial_history_falls_back_to_pre_final_window_scale():
    rng = np.random.default_rng(0)
    y = np.concatenate([np.full(150, 10.0), 10 + np.cumsum(rng.normal(0, 1, 50))])
    data = pd.DataFrame({"ds": pd.date_range("2024-01-01", periods=200), "y": y})
    plan = plan_backtest(200, 14, 1)  # first window trains on 130 points: all flat
    assert plan.windows[0].train_end == 130
    result = run_backtest(data, "D", plan, [(SPEC["Naive"], Eligibility(True, 1))])
    assert result.summary.mase_scale_source == "pre_final_window" and result.summary.mase_scale > 0


def test_fully_flat_history_leaves_mase_undefined_not_crashing():
    data = pd.DataFrame({"ds": pd.date_range("2024-01-01", periods=100), "y": np.full(100, 3.0)})
    plan = plan_backtest(100, 14, 1)
    result = run_backtest(data, "D", plan, [(SPEC["Naive"], Eligibility(True, 1))])
    assert result.summary.mase_scale is None and result.summary.mase_scale_source == "undefined"
    assert (
        result.summary.models[0].metrics.mase is None
        and result.summary.models[0].metrics.window_mase is None
    )
