import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from forecast import pipeline
from forecast.diagnostics import WARNING_CODES
from forecast.outputs import write_artifacts
from forecast.pipeline import FORECAST_COLUMNS, run_forecast
from forecast.schema import NeedsInputError, RefusedError, RunResult
from tests import synthetic

pytestmark = pytest.mark.slow
EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@pytest.fixture(scope="module")
def runs():
    return {name: run_forecast(EXAMPLES / f"{name}.csv") for name in
            ("retail_sales", "saas_revenue", "website_traffic", "inventory_demand")}  # fmt: skip


def csv(tmp_path, df, name="d.csv"):
    p = tmp_path / name
    df.to_csv(p, index=False)
    return p


def check_forecast_invariants(outcome, horizon):
    f = outcome.forecast
    assert list(f.columns) == FORECAST_COLUMNS and len(f) == horizon
    assert (f["lo_95"] <= f["lo_80"]).all() and (f["lo_80"] <= f["forecast"]).all()
    assert (f["forecast"] <= f["hi_80"]).all() and (f["hi_80"] <= f["hi_95"]).all()
    assert np.isfinite(f[["forecast", "lo_80", "hi_80", "lo_95", "hi_95"]].to_numpy()).all()
    assert (f["model"] == outcome.result.forecast.model).all()
    ds = pd.DatetimeIndex(f["ds"])
    assert ds.is_monotonic_increasing and ds.is_unique


# ------------------------------------------------------------ the examples, end to end


def test_every_example_produces_a_valid_complete_result(runs):
    for name, outcome in runs.items():
        r = outcome.result
        check_forecast_invariants(outcome, r.forecast.horizon)
        assert r.status in ("ok", "ok_with_warnings"), name
        assert RunResult.model_validate_json(r.model_dump_json()) == r, name
        assert {w.code for w in r.warnings} <= set(WARNING_CODES), name
        assert r.forecast.total_interval is None
        assert r.meta.statsforecast_version and r.meta.elapsed_seconds >= 0


def test_forecast_starts_the_period_after_the_data_and_is_contiguous(runs):
    last = {
        "retail_sales": "2025-12-31",
        "website_traffic": "2025-10-27",
        "inventory_demand": "2025-10-27",
    }
    for name, end in last.items():
        ds = pd.DatetimeIndex(runs[name].forecast["ds"])
        assert ds[0] == pd.Timestamp(end) + pd.offsets.Day(1), name
        assert (np.diff(ds.values) == np.timedelta64(1, "D")).all(), name
    saas = pd.DatetimeIndex(runs["saas_revenue"].forecast["ds"])
    assert saas[0] == pd.Timestamp("2026-01-01") and len(saas) == 12 and pd.infer_freq(saas) == "MS"


def test_default_horizons_by_frequency(runs):
    assert runs["retail_sales"].result.forecast.horizon == 28
    assert runs["saas_revenue"].result.forecast.horizon == 12


def test_selection_and_forecast_agree_and_reasons_are_reported(runs):
    r = runs["retail_sales"].result
    assert (
        r.selection.winner == r.forecast.model == "AutoETS"
        and r.selection.reason == "beat_baseline_by_margin"
    )
    web = runs["website_traffic"].result
    assert web.selection.winner_kind == "baseline"
    assert {"BASELINE_WON", "POOR_BACKTEST"} <= {w.code for w in web.warnings}


def test_intermittent_example_runs_baselines_only_and_never_goes_negative(runs):
    o = runs["inventory_demand"]
    assert o.result.selection.reason == "only_baselines_ran"
    assert (o.forecast[["forecast", "lo_80", "lo_95"]] >= 0).all().all()
    assert o.result.forecast.clipped_at_zero and "FORECAST_CLIPPED" in {
        w.code for w in o.result.warnings
    }
    assert "INTERMITTENT" in {w.code for w in o.result.warnings}


def test_summary_arithmetic(runs):
    o = runs["retail_sales"]
    f, data_total = o.result.forecast, pd.read_csv(EXAMPLES / "retail_sales.csv")["sales"]
    assert f.total == pytest.approx(o.forecast["forecast"].sum())
    assert f.previous_total == pytest.approx(data_total.iloc[-f.horizon :].sum())
    assert f.change_vs_prior == pytest.approx(f.total / f.previous_total - 1)
    assert (
        f.mean == pytest.approx(o.forecast["forecast"].mean())
        and f.last_observed == data_total.iloc[-1]
    )


def _stable(result):
    """The result minus its two timing fields (``meta`` and each model's ``fit_seconds``)."""
    doc = json.loads(result.model_dump_json())
    doc.pop("meta")
    for m in doc["backtest"]["models"]:
        m.pop("fit_seconds")
    return doc


def test_a_run_is_deterministic():
    a = run_forecast(EXAMPLES / "saas_revenue.csv")
    b = run_forecast(EXAMPLES / "saas_revenue.csv")
    pd.testing.assert_frame_equal(a.forecast, b.forecast)
    pd.testing.assert_frame_equal(a.backtest, b.backtest)
    assert _stable(a.result) == _stable(b.result)


@pytest.mark.parametrize("horizon", [1, 7, 30, 60])
def test_horizon_is_exact(tmp_path, horizon):
    outcome = run_forecast(csv(tmp_path, synthetic.trend_seasonality(400)), horizon=horizon)
    check_forecast_invariants(outcome, horizon)
    assert outcome.result.forecast.horizon == horizon


def test_intervals_widen_with_the_horizon(tmp_path):
    f = run_forecast(csv(tmp_path, synthetic.random_walk(300)), horizon=20).forecast
    widths = (f["hi_95"] - f["lo_95"]).to_numpy()
    assert widths[-1] > widths[0]


# ------------------------------------------------------------ series selection


def test_multi_series_file_needs_input_then_runs_with_where_or_agg():
    path = EXAMPLES / "multi_store_sales.csv"
    with pytest.raises(NeedsInputError) as e:
        run_forecast(path)
    assert e.value.ambiguities[0].kind == "series"
    sliced = run_forecast(path, where={"store": "North", "product": "Widget"}, horizon=14)
    assert sliced.forecast["series"].iloc[0] == "units_sold[store=North,product=Widget]"
    total = run_forecast(path, agg="sum", horizon=14)
    assert total.forecast["series"].iloc[0] == "units_sold[sum]"
    assert total.result.forecast.mean > sliced.result.forecast.mean * 3  # 4 series summed


# ------------------------------------------------------------ refusals


def test_constant_series_is_refused(tmp_path):
    with pytest.raises(RefusedError) as e:
        run_forecast(csv(tmp_path, synthetic.constant()))
    assert e.value.code == "CONSTANT_SERIES"


def test_too_little_data_is_refused(tmp_path):
    with pytest.raises(RefusedError) as e:
        run_forecast(csv(tmp_path, synthetic.linear_trend(20)))
    assert e.value.code == "INSUFFICIENT_DATA"


def test_horizon_too_long_for_history_is_refused_with_the_maximum(tmp_path):
    with pytest.raises(RefusedError) as e:
        run_forecast(csv(tmp_path, synthetic.linear_trend(60)), horizon=50)
    assert e.value.code == "HORIZON_TOO_LONG" and e.value.details["max_horizon"] == 12


def test_short_history_shortens_the_backtest_horizon_but_forecasts_the_full_horizon(tmp_path):
    o = run_forecast(csv(tmp_path, synthetic.trend_seasonality(48)), horizon=14)
    assert (
        o.result.backtest.plan.shortened
        and o.result.forecast.horizon == 14
        and len(o.forecast) == 14
    )
    codes = {w.code for w in o.result.warnings}
    assert {"BACKTEST_HORIZON_SHORTENED", "SHORT_HISTORY"} <= codes


# ------------------------------------------------------------ failure handling


def test_winner_refit_failure_falls_back_to_the_next_ranked_model(tmp_path):
    from forecast.models import build_model

    calls = {}

    def flaky(spec, season_length):
        calls[spec.name] = calls.get(spec.name, 0) + 1
        if (
            spec.name == "AutoETS" and calls[spec.name] > 1
        ):  # fine in the backtest, dies on the refit
            raise RuntimeError("refit exploded")
        return build_model(spec, season_length)

    o = run_forecast(csv(tmp_path, synthetic.trend_seasonality(300)), horizon=14, build=flaky)
    r = o.result
    assert r.selection.winner == "AutoETS"  # the selection is not rewritten
    assert r.forecast.model != "AutoETS" and r.forecast.model == r.selection.ranking[1].name
    assert "WINNER_REFIT_FAILED" in {w.code for w in r.warnings} and r.status == "ok_with_warnings"
    check_forecast_invariants(o, 14)


def test_a_model_failing_in_the_backtest_is_reported_not_fatal(tmp_path):
    from forecast.models import build_model

    def broken(spec, season_length):
        if spec.name == "AutoARIMA":
            raise RuntimeError("no arima today")
        return build_model(spec, season_length)

    o = run_forecast(csv(tmp_path, synthetic.trend_seasonality(300)), horizon=14, build=broken)
    assert "MODEL_FAILED" in {w.code for w in o.result.warnings}
    assert next(m for m in o.result.backtest.models if m.name == "AutoARIMA").status == "failed"


# ------------------------------------------------------------ clipping


def test_non_negative_history_never_forecasts_below_zero(tmp_path):
    df = synthetic.linear_trend(n=95, slope=-1.0, intercept=100.0, noise=1.0)  # heads to ~5, then 0
    o = run_forecast(csv(tmp_path, df), horizon=28)
    assert (o.forecast[["forecast", "lo_80", "lo_95"]] >= 0).all().all()
    assert o.result.forecast.clipped_at_zero


def test_series_with_negatives_is_not_clipped(tmp_path):
    o = run_forecast(csv(tmp_path, synthetic.white_noise(level=0.0, noise=5.0)), horizon=14)
    assert not o.result.forecast.clipped_at_zero and (o.forecast["lo_95"] < 0).any()
    assert "NEGATIVE_VALUES" in {w.code for w in o.result.warnings}


# ------------------------------------------------------------ interval calibration end to end


def baselines_only(monkeypatch):
    real = pipeline.eligible_models

    def only(ctx):
        run, skipped = real(ctx)
        return [x for x in run if x[0].kind == "baseline"], skipped + [
            x for x in run if x[0].kind != "baseline"
        ]

    monkeypatch.setattr(pipeline, "eligible_models", only)


def test_badly_calibrated_baseline_intervals_are_widened(monkeypatch, tmp_path):
    baselines_only(monkeypatch)
    o = run_forecast(csv(tmp_path, synthetic.linear_trend(250)), horizon=14)
    i = o.result.intervals
    assert (
        i.method == "calibrated" and i.native_coverage_80 < 0.6 and i.calibrated_coverage_80 >= 0.8
    )
    codes = {w.code for w in o.result.warnings}
    assert "INTERVALS_CALIBRATED" in codes and "LOW_COVERAGE" not in codes  # superseded, not both


def test_calibration_improves_out_of_sample_coverage(monkeypatch, tmp_path):
    """The reason calibration exists: on a trend, baseline intervals miss almost everything."""
    baselines_only(monkeypatch)
    horizon, hits_final, hits_native = 14, [], []
    real = pipeline.intervals.calibrate
    for seed in range(5):
        df = synthetic.linear_trend(250, seed=seed)
        p = csv(tmp_path, df.iloc[:-horizon])
        actual = df["value"].to_numpy()[-horizon:]
        for calibrate, bucket in (
            (real, hits_final),
            (lambda rows, fc, m: (fc, real(rows, fc, m)[1], []), hits_native),
        ):
            monkeypatch.setattr(pipeline.intervals, "calibrate", calibrate)
            f = run_forecast(p, horizon=horizon).forecast
            bucket.append(np.mean((actual >= f["lo_80"]) & (actual <= f["hi_80"])))
    assert np.mean(hits_native) < 0.4 and np.mean(hits_final) >= 0.75


# ------------------------------------------------------------ artifacts


def test_write_artifacts_creates_a_consistent_run_directory(runs, tmp_path):
    outcome = runs["saas_revenue"]
    result = write_artifacts(outcome, tmp_path / "run")
    out = tmp_path / "run"
    assert sorted(p.name for p in out.iterdir()) == [
        "backtest.csv",
        "forecast.csv",
        "forecast.png",
        "profile.json",
        "result.json",
    ]
    assert result.artifacts.directory == str(out.resolve())
    on_disk = RunResult.model_validate_json((out / "result.json").read_text())
    assert on_disk == result
    assert json.loads((out / "profile.json").read_text()) == json.loads(
        result.profile.model_dump_json()
    )
    fc = pd.read_csv(out / "forecast.csv")
    assert list(fc.columns) == FORECAST_COLUMNS and len(fc) == result.forecast.horizon
    assert fc["ds"].iloc[0].endswith("T00:00:00")
    np.testing.assert_allclose(fc["forecast"], outcome.forecast["forecast"])
    bt = pd.read_csv(out / "backtest.csv")
    assert len(bt) == len(outcome.backtest)
