import pytest

from forecast.backtest import (
    MAX_WINDOWS,
    MIN_WINDOWS,
    max_full_horizon,
    min_train_size,
    plan_backtest,
    resolve_horizon,
)
from forecast.schema import RefusedError


def codes(plan):
    return {n.code for n in plan.notices}


def test_typical_daily_plan():
    plan = plan_backtest(1004, 30, season_length=7)
    assert (plan.backtest_horizon, plan.n_windows, plan.step, plan.min_train) == (30, 5, 30, 24)
    assert not plan.shortened and plan.notices == []
    assert [(w.train_end, w.test_end) for w in plan.windows] == [
        (854, 884),
        (884, 914),
        (914, 944),
        (944, 974),
        (974, 1004),
    ]


def test_min_train_is_two_cycles_or_24():
    assert min_train_size(1) == 24 and min_train_size(7) == 24 and min_train_size(12) == 24
    assert min_train_size(24) == 48 and min_train_size(52) == 104


def test_three_windows_when_history_is_tight():
    plan = plan_backtest(24 + 3 * 28, 28, season_length=7)  # exactly enough
    assert plan.n_windows == 3 and not plan.shortened and "FEW_BACKTEST_WINDOWS" in codes(plan)


def test_horizon_shortened_with_warning_instead_of_refusing():
    plan = plan_backtest(60, 14, season_length=7)  # full horizon would give 2 windows
    assert plan.shortened and plan.backtest_horizon == 12 and plan.n_windows == 3
    assert "BACKTEST_HORIZON_SHORTENED" in codes(plan)
    assert plan.horizon == 14  # the forecast itself is still 14 steps


def test_refuses_when_shortening_would_fall_below_floor():
    with pytest.raises(RefusedError) as e:
        plan_backtest(40, 30, season_length=1)  # supported 5, floor 15
    assert e.value.code == "HORIZON_TOO_LONG"
    assert e.value.details["max_horizon"] == 5 and e.value.details["required"] == 24 + 3 * 15


def test_floor_is_at_least_one_season():
    plan = plan_backtest(60, 20, season_length=12)  # supported 12 == floor max(12, 10): allowed
    assert plan.shortened and plan.backtest_horizon == 12
    with pytest.raises(RefusedError) as e:
        plan_backtest(52, 20, season_length=12)  # supported 9 < floor 12
    assert e.value.code == "HORIZON_TOO_LONG"


def test_refuses_insufficient_data():
    with pytest.raises(RefusedError) as e:
        plan_backtest(26, 1)
    assert e.value.code == "INSUFFICIENT_DATA" and e.value.details["required"] == 27


def test_short_horizon_cannot_be_shortened_further():
    assert plan_backtest(40, 3, season_length=12).n_windows == 5  # 3-step windows fit easily
    with pytest.raises(RefusedError) as e:
        plan_backtest(
            30, 3, season_length=12
        )  # supported 2 < 3, and the floor is capped at the horizon
    assert e.value.code == "HORIZON_TOO_LONG"


def test_long_horizon_warning():
    plan = plan_backtest(200, 50, season_length=7)
    assert "HORIZON_LONG" in codes(plan)
    assert "HORIZON_LONG" not in codes(plan_backtest(1004, 30, season_length=7))


def test_bad_horizon_is_a_bad_argument():
    with pytest.raises(RefusedError) as e:
        plan_backtest(100, 0)
    assert e.value.code == "BAD_ARGUMENT"


@pytest.mark.parametrize("n_obs", [27, 30, 45, 60, 100, 157, 400, 1004])
@pytest.mark.parametrize("horizon", [1, 3, 7, 14, 30, 90])
@pytest.mark.parametrize("season", [1, 5, 7, 12, 24, 52])
def test_plan_invariants_hold_everywhere(n_obs, horizon, season):
    try:
        plan = plan_backtest(n_obs, horizon, season)
    except RefusedError as exc:
        assert exc.code in {"INSUFFICIENT_DATA", "HORIZON_TOO_LONG"}
        # a refusal must be justified: shortening to the floor really was impossible
        floor = min(horizon, max(season, -(-horizon // 2)))
        assert (n_obs - min_train_size(season)) // MIN_WINDOWS < floor
        return
    h = plan.backtest_horizon
    assert MIN_WINDOWS <= plan.n_windows <= MAX_WINDOWS
    assert h <= horizon and plan.step == h and (plan.shortened == (h < horizon))
    assert plan.windows[-1].test_end == n_obs  # the most recent data is always tested
    assert plan.windows[0].train_end >= plan.min_train
    for prev, cur in zip(plan.windows, plan.windows[1:]):
        assert cur.test_start == prev.test_end  # contiguous, non-overlapping
    for w in plan.windows:
        assert w.train_end == w.test_start and w.test_end - w.test_start == h
    if h < horizon:
        assert h >= min(horizon, max(season, -(-horizon // 2)))  # never below the floor


def test_resolve_horizon_uses_request_verbatim():
    assert resolve_horizon(45, "D", 1000, 7) == (45, [])


def test_resolve_horizon_frequency_defaults():
    for freq, expected in [
        ("D", 28),
        ("W-SUN", 13),
        ("MS", 12),
        ("ME", 12),
        ("QE-DEC", 4),
        ("h", 24),
        ("B", 20),
    ]:
        assert resolve_horizon(None, freq, 5000, 1)[0] == expected


def test_resolve_horizon_default_reduced_to_what_history_supports():
    h, notices = resolve_horizon(None, "MS", 48, 12)  # default 12, supported (48-24)//3 = 8
    assert h == max_full_horizon(48, 12) == 8
    assert [n.code for n in notices] == ["HORIZON_DEFAULT_REDUCED"]
    plan = plan_backtest(48, h, 12)
    assert not plan.shortened  # the reduced default is always fully backtestable


def test_resolve_horizon_refuses_when_nothing_is_backtestable():
    with pytest.raises(RefusedError) as e:
        resolve_horizon(None, "D", 20, 1)
    assert e.value.code == "INSUFFICIENT_DATA"


def test_resolve_horizon_rejects_nonpositive_request():
    with pytest.raises(RefusedError) as e:
        resolve_horizon(-3, "D", 500, 7)
    assert e.value.code == "BAD_ARGUMENT"
