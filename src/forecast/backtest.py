"""Rolling-origin backtest planning.

Windows are expanding-train / fixed-horizon / non-overlapping test blocks packed against the
end of the series:

    TRAIN ───────────── TEST
    TRAIN ───────────────── TEST
    TRAIN ───────────────────── TEST

Planning is pure arithmetic over the series length; model fitting lives elsewhere.
"""

from __future__ import annotations

import math

from forecast.schema import BacktestPlan, BacktestWindow, Notice, RefusedError

MIN_WINDOWS = 3
MAX_WINDOWS = 5
MIN_TRAIN_FLOOR = 24
LONG_HORIZON_FRACTION = 0.20  # warn when horizon > this share of the history

DEFAULT_HORIZONS = {
    "h": 24,
    "D": 28,
    "B": 20,
    "W": 13,
    "MS": 12,
    "ME": 12,
    "QS": 4,
    "QE": 4,
    "YS": 3,
    "YE": 3,
}


def min_train_size(season_length: int) -> int:
    """Shortest training window: two seasonal cycles, and never fewer than 24 points."""
    return max(2 * max(season_length, 1), MIN_TRAIN_FLOOR)


def max_full_horizon(n_obs: int, season_length: int) -> int:
    """Longest horizon that still yields MIN_WINDOWS non-overlapping windows."""
    return (n_obs - min_train_size(season_length)) // MIN_WINDOWS


def resolve_horizon(
    requested: int | None, frequency: str, n_obs: int, season_length: int
) -> tuple[int, list[Notice]]:
    """Pick the forecast horizon: the user's, or a frequency default capped to what history supports."""
    if requested is not None:
        if requested < 1:
            raise RefusedError("BAD_ARGUMENT", f"--horizon must be at least 1, got {requested}.")
        return requested, []
    default = DEFAULT_HORIZONS.get(frequency.split("-")[0], 12)
    cap = max_full_horizon(n_obs, season_length)
    if cap >= default:
        return default, []
    if cap < 1:
        raise RefusedError(
            "INSUFFICIENT_DATA",
            f"{n_obs} observations are too few to backtest even a 1-step forecast; "
            f"need at least {min_train_size(season_length) + MIN_WINDOWS}.",
            n_obs=n_obs,
            required=min_train_size(season_length) + MIN_WINDOWS,
        )
    notice = Notice(code="HORIZON_DEFAULT_REDUCED", severity="info",
                    message=f"Default horizon of {default} reduced to {cap} so that history can back-test it.",
                    details={"default": default, "used": cap})  # fmt: skip
    return cap, [notice]


def plan_backtest(n_obs: int, horizon: int, season_length: int = 1) -> BacktestPlan:
    """Lay out the rolling-origin windows, shortening the backtest horizon only as a last resort.

    * Preferred: backtest at the full ``horizon`` with 3 to 5 windows.
    * If history cannot support 3 windows at that horizon, shorten the backtest horizon down
      to a floor of ``max(season_length, ceil(horizon / 2))`` and say so.
    * Below that floor the evidence would not describe the forecast being asked for: refuse.
    """
    if horizon < 1:
        raise RefusedError("BAD_ARGUMENT", f"horizon must be at least 1, got {horizon}.")
    min_train = min_train_size(season_length)
    notices: list[Notice] = []
    supported = (n_obs - min_train) // MIN_WINDOWS  # longest horizon with 3 windows

    if supported >= horizon:
        h_bt = horizon
    else:
        floor = min(horizon, max(season_length, math.ceil(horizon / 2)))
        if supported < 1:
            raise RefusedError(
                "INSUFFICIENT_DATA",
                f"{n_obs} observations are too few to backtest: need at least "
                f"{min_train + MIN_WINDOWS} (two seasonal cycles or 24 points, plus 3 test windows).",
                n_obs=n_obs,
                required=min_train + MIN_WINDOWS,
            )
        if supported < floor:
            raise RefusedError(
                "HORIZON_TOO_LONG",
                f"A {horizon}-step forecast cannot be validated with {n_obs} observations: "
                f"at least {min_train + MIN_WINDOWS * floor} are needed, or use a horizon of "
                f"{supported} or less.",
                n_obs=n_obs,
                horizon=horizon,
                max_horizon=supported,
                required=min_train + MIN_WINDOWS * floor,
            )
        h_bt = supported
        notices.append(Notice(code="BACKTEST_HORIZON_SHORTENED", severity="warn",
                              message=f"History is too short to back-test {horizon} steps ahead; models were "
                                      f"scored on {h_bt}-step forecasts instead. Accuracy at the full horizon "
                                      "is likely worse than measured.",
                              details={"horizon": horizon, "backtest_horizon": h_bt}))  # fmt: skip

    n_windows = min(MAX_WINDOWS, (n_obs - min_train) // h_bt)
    windows = []
    for w in range(n_windows):
        test_start = n_obs - (n_windows - w) * h_bt
        windows.append(BacktestWindow(index=w, train_end=test_start, test_start=test_start,
                                      test_end=test_start + h_bt))  # fmt: skip

    if horizon > LONG_HORIZON_FRACTION * n_obs:
        notices.append(Notice(code="HORIZON_LONG", severity="warn",
                              message=f"The {horizon}-step horizon is more than {LONG_HORIZON_FRACTION:.0%} of "
                                      f"the {n_obs} observations of history; long-range forecasts are unreliable.",
                              details={"horizon": horizon, "n_obs": n_obs}))  # fmt: skip
    if n_windows < MAX_WINDOWS:
        notices.append(Notice(code="FEW_BACKTEST_WINDOWS", severity="info",
                              message=f"Model selection rests on {n_windows} backtest windows; "
                                      "with so few, rankings are noisy.",
                              details={"n_windows": n_windows}))  # fmt: skip
    return BacktestPlan(
        horizon=horizon,
        backtest_horizon=h_bt,
        n_windows=n_windows,
        step=h_bt,
        min_train=min_train,
        season_length=season_length,
        shortened=h_bt < horizon,
        windows=windows,
        notices=notices,
    )
