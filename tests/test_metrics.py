import math

import numpy as np
import pytest

from forecast import metrics

ACTUAL = [3, 5, 2, 7]
FORECAST = [2, 5, 4, 8]  # errors: -1, 0, 2, 1
INSAMPLE = [1, 3, 2, 5, 4]


def test_mae_hand_computed():
    assert metrics.mae(ACTUAL, FORECAST) == pytest.approx(1.0)  # (1+0+2+1)/4


def test_rmse_hand_computed():
    assert metrics.rmse(ACTUAL, FORECAST) == pytest.approx(math.sqrt(1.5))  # (1+0+4+1)/4


def test_smape_hand_computed_percent():
    # 200 * mean(1/5, 0/10, 2/6, 1/15) = 200 * 0.15
    assert metrics.smape(ACTUAL, FORECAST) == pytest.approx(30.0)


def test_smape_both_zero_is_perfect_and_one_zero_is_maximal():
    assert metrics.smape([0, 0], [0, 0]) == 0.0
    assert metrics.smape([0.0], [5.0]) == pytest.approx(200.0)
    assert metrics.smape([5.0], [0.0]) == pytest.approx(200.0)


def test_smape_is_symmetric():
    assert metrics.smape([10.0], [20.0]) == pytest.approx(metrics.smape([20.0], [10.0]))


def test_mase_scale_and_value_non_seasonal():
    assert metrics.mase_scale(INSAMPLE, 1) == pytest.approx(1.75)  # mean(2, 1, 3, 1)
    assert metrics.mase(ACTUAL, FORECAST, INSAMPLE, 1) == pytest.approx(1.0 / 1.75)


def test_mase_seasonal_scale():
    assert metrics.mase_scale(INSAMPLE, 2) == pytest.approx(5 / 3)  # mean(1, 2, 2)
    assert metrics.mase(ACTUAL, FORECAST, INSAMPLE, 2) == pytest.approx(0.6)


def test_mase_below_one_means_beating_the_naive_forecast():
    train = [10, 12, 11, 13, 12, 14]
    assert metrics.mase([15, 16], [15.2, 15.9], train, 1) < 1
    assert metrics.mase([15, 16], [10, 30], train, 1) > 1


def test_mase_defined_with_zeros_where_smape_is_not_meaningful():
    train = [0, 3, 0, 0, 5, 0, 2, 0]
    assert metrics.mase([0, 4], [0, 3], train, 1) is not None


def test_mase_undefined_for_flat_history():
    assert metrics.mase_scale([4, 4, 4, 4], 1) is None
    assert metrics.mase([1], [2], [4, 4, 4, 4], 1) is None


def test_mase_scale_needs_more_points_than_period():
    with pytest.raises(ValueError):
        metrics.mase_scale([1, 2, 3], 3)


def test_perfect_forecast_scores_zero():
    for fn in (metrics.mae, metrics.rmse, metrics.smape):
        assert fn(ACTUAL, ACTUAL) == 0.0
    assert metrics.mase(ACTUAL, ACTUAL, INSAMPLE) == 0.0


def test_coverage():
    assert metrics.coverage([1, 2, 3, 4], [0, 0, 4, 0], [2, 1, 5, 4]) == pytest.approx(0.5)


@pytest.mark.parametrize("fn", [metrics.mae, metrics.rmse, metrics.smape])
def test_input_validation(fn):
    with pytest.raises(ValueError):
        fn([1, 2], [1])
    with pytest.raises(ValueError):
        fn([], [])


def test_rmse_penalises_large_errors_more_than_mae():
    a = np.zeros(4)
    even, spiky = np.full(4, 2.0), np.array([0, 0, 0, 8.0])  # same MAE (2.0)
    assert metrics.mae(a, even) == metrics.mae(a, spiky)
    assert metrics.rmse(a, spiky) > metrics.rmse(a, even)


def test_agrees_with_utilsforecast():
    losses = pytest.importorskip("utilsforecast.losses")
    import pandas as pd

    df = pd.DataFrame({"unique_id": "a", "y": ACTUAL, "m": FORECAST}).astype(
        {"y": float, "m": float}
    )
    train = pd.DataFrame({"unique_id": "a", "y": INSAMPLE}).astype({"y": float})
    col = lambda r: float(r.iloc[0, 1])
    assert metrics.mae(ACTUAL, FORECAST) == pytest.approx(col(losses.mae(df, ["m"])))
    assert metrics.rmse(ACTUAL, FORECAST) == pytest.approx(col(losses.rmse(df, ["m"])))
    # utilsforecast's smape omits the factor 2 and the percent scale (0..1 instead of 0..200)
    assert metrics.smape(ACTUAL, FORECAST) == pytest.approx(200 * col(losses.smape(df, ["m"])))
    for m in (1, 2):
        ref = col(losses.mase(df, ["m"], seasonality=m, train_df=train))
        assert metrics.mase(ACTUAL, FORECAST, INSAMPLE, m) == pytest.approx(ref)
