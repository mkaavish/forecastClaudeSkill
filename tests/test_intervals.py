import numpy as np
import pandas as pd
import pytest

from forecast import intervals

RNG = np.random.default_rng(0)


def backtest_rows(n=120, sigma=1.0, width_sigma=1.0, bias=0.0, seed=0):
    """Backtest rows whose native 80% interval is +-1.2816*width_sigma around the forecast.

    Errors are N(bias, sigma): with width_sigma == sigma the native intervals are correct.
    """
    rng = np.random.default_rng(seed)
    yhat = np.full(n, 100.0)
    y = yhat + rng.normal(bias, sigma, n)
    z80, z95 = 1.2816, 1.96
    return pd.DataFrame({
        "y": y, "yhat": yhat,
        "lo_80": yhat - z80 * width_sigma, "hi_80": yhat + z80 * width_sigma,
        "lo_95": yhat - z95 * width_sigma, "hi_95": yhat + z95 * width_sigma,
    })  # fmt: skip


def forecast_rows(h=14):
    steps = np.arange(1, h + 1)
    yhat = np.full(h, 100.0)
    half80, half95 = 1.28 * np.sqrt(steps), 1.96 * np.sqrt(steps)  # widening with the horizon
    return pd.DataFrame({
        "series": "s", "ds": pd.date_range("2026-01-01", periods=h), "forecast": yhat,
        "lo_80": yhat - half80, "hi_80": yhat + half80, "lo_95": yhat - half95, "hi_95": yhat + half95,
        "model": "M",
    })  # fmt: skip


def test_well_calibrated_intervals_are_left_alone():
    rows, fc = backtest_rows(), forecast_rows()
    out, info, notices = intervals.calibrate(rows, fc, "M")
    assert info.method == "native" and notices == [] and out.equals(fc)
    assert 0.6 <= info.native_coverage_80 <= 0.95


def test_over_wide_intervals_are_never_narrowed():
    rows = backtest_rows(width_sigma=4.0)  # native coverage ~100%
    _, info, notices = intervals.calibrate(rows, forecast_rows(), "M")
    assert info.method == "native" and notices == [] and info.native_coverage_80 > 0.95


def test_moderate_undercoverage_is_not_recalibrated():
    rows = backtest_rows(width_sigma=0.8)  # ~68% coverage: noisy territory, left alone
    assert 0.6 <= intervals.calibrate(rows, forecast_rows(), "M")[1].native_coverage_80 < 0.8
    assert intervals.calibrate(rows, forecast_rows(), "M")[1].method == "native"


def test_gross_undercoverage_is_widened_to_nominal_coverage():
    rows = backtest_rows(width_sigma=0.25)  # intervals 4x too narrow: coverage ~ 0.25
    out, info, notices = intervals.calibrate(rows, forecast_rows(), "SeasonalNaive")
    assert info.method == "calibrated" and info.native_coverage_80 < 0.4
    assert info.factor_80 > 1 and info.factor_95 > 1
    assert info.calibrated_coverage_80 >= 0.80 and info.calibrated_coverage_95 >= 0.95
    assert [n.code for n in notices] == ["INTERVALS_CALIBRATED"] and "SeasonalNaive" in notices[
        0
    ].message
    # widths grew by exactly the factor, on each side
    fc = forecast_rows()
    np.testing.assert_allclose(
        out["hi_80"] - out["forecast"], info.factor_80 * (fc["hi_80"] - fc["forecast"])
    )
    np.testing.assert_allclose(
        out["forecast"] - out["lo_95"], info.factor_95 * (fc["forecast"] - fc["lo_95"])
    )


def test_calibration_keeps_the_shape_nesting_and_point_forecast():
    out, _, _ = intervals.calibrate(backtest_rows(width_sigma=0.3), forecast_rows(), "M")
    fc = forecast_rows()
    assert (out["forecast"] == fc["forecast"]).all() and (out["ds"] == fc["ds"]).all()
    assert (out["lo_95"] <= out["lo_80"]).all() and (out["lo_80"] <= out["forecast"]).all()
    assert (out["forecast"] <= out["hi_80"]).all() and (out["hi_80"] <= out["hi_95"]).all()
    widths = (out["hi_80"] - out["lo_80"]).to_numpy()
    assert (np.diff(widths) > 0).all()  # still grows with the horizon, as the model said


def test_asymmetric_native_intervals_stay_asymmetric():
    fc = forecast_rows()
    fc["hi_80"] = fc["forecast"] + 2 * (fc["hi_80"] - fc["forecast"])
    fc["hi_95"] = fc["forecast"] + 2 * (fc["hi_95"] - fc["forecast"])
    out, _, _ = intervals.calibrate(backtest_rows(width_sigma=0.3), fc, "M")
    up, down = out["hi_80"] - out["forecast"], out["forecast"] - out["lo_80"]
    np.testing.assert_allclose(up / down, 2.0)


def test_one_sided_errors_scale_by_the_side_they_fell_on():
    rows = backtest_rows(width_sigma=0.4, bias=3.0)  # actuals sit above the forecast
    _, info, _ = intervals.calibrate(rows, forecast_rows(), "M")
    assert info.method == "calibrated" and info.calibrated_coverage_80 >= 0.8


def test_too_few_backtest_points_leave_native_intervals_with_a_note():
    out, info, notices = intervals.calibrate(
        backtest_rows(n=20, width_sigma=0.2), forecast_rows(), "M"
    )
    assert info.method == "native" and notices == [] and "only 20 backtest points" in info.note
    assert out.equals(forecast_rows())


def test_unusably_narrow_intervals_are_not_rescaled():
    rows = backtest_rows(width_sigma=0.01)  # would need a factor of ~100
    _, info, notices = intervals.calibrate(rows, forecast_rows(), "M")
    assert info.method == "native" and notices == [] and "could not be rescaled" in info.note


def test_zero_width_native_intervals_are_handled():
    rows = backtest_rows()
    rows[["lo_80", "hi_80", "lo_95", "hi_95"]] = rows[["yhat"]].to_numpy().repeat(4, axis=1)
    _, info, _ = intervals.calibrate(rows, forecast_rows(), "M")
    assert info.method == "native"  # infinite ratios -> unusable, no crash


def test_conformal_factor_uses_the_finite_sample_quantile():
    rows = backtest_rows(width_sigma=1.0)
    rows["y"] = rows["yhat"] + np.linspace(0.01, 1.0, len(rows)) * np.where(
        np.arange(len(rows)) % 2, 1, -1
    )
    ratio = np.sort(np.abs(rows["y"] - rows["yhat"]) / 1.2816)
    k = int(np.ceil((len(rows) + 1) * 0.80))
    assert intervals.conformal_factor(rows, 80) == pytest.approx(max(ratio[k - 1], 1.0))


def test_factor_is_never_below_one():
    assert intervals.conformal_factor(backtest_rows(width_sigma=5.0), 80) == 1.0
