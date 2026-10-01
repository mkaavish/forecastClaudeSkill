"""Series-level refusal rules: cases where forecasting is statistically inappropriate.

Backtest-dependent warnings (poor MASE, baseline won, wide intervals, low coverage) arrive
with the selection step in a later phase; this module holds what can be decided from the
profile alone.
"""

from __future__ import annotations

from forecast.schema import ProfileReport, RefusedError


def check_forecastable(profile: ProfileReport) -> None:
    """Raise ``RefusedError`` when the data cannot support any meaningful forecast."""
    if profile.constant:
        raise RefusedError(
            "CONSTANT_SERIES",
            f"Every observation equals {profile.stats.min:g}. A statistical forecast would only "
            "repeat that value and its uncertainty cannot be estimated from the data.",
            value=profile.stats.min,
        )
