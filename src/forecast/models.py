"""Model registry: which models exist, why, and when each is allowed to run.

Phase 3 defines only the declarative part (specs and eligibility rules, no fitting).
Every model must justify its place:

* Naive            - the minimum bar; optimal for a random walk.
* SeasonalNaive    - the bar for seasonal data; only meaningful when a period was detected.
* HistoricAverage  - the right baseline for stationary noise; stops trends being "found" in nothing.
* AutoETS          - strong general default for trend and seasonality.
* AutoARIMA        - captures autocorrelation structure ETS cannot.
* AutoTheta        - cheap and robust on short series; drop it if benchmarks show it never wins.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from forecast.schema import ProfileReport

MAX_SEASON_FOR_ETS_ARIMA = (
    24  # longer periods (168 hourly, 365 daily, 52 weekly) are impractically slow
)


@dataclass(frozen=True)
class ModelSpec:
    name: str
    kind: Literal["baseline", "complex"]
    simplicity: int  # lower = simpler; the deterministic tie-breaker in selection
    needs_season: bool = False  # only runs when a seasonal period was detected
    max_season_length: int | None = None  # longer periods are modelled as non-seasonal
    handles_intermittent: bool = False  # complex models are skipped on zero-heavy data
    why: str = ""


REGISTRY: tuple[ModelSpec, ...] = (
    ModelSpec("Naive", "baseline", 0, handles_intermittent=True, why="random-walk baseline"),
    ModelSpec(
        "SeasonalNaive",
        "baseline",
        1,
        needs_season=True,
        handles_intermittent=True,
        why="seasonal baseline",
    ),
    ModelSpec(
        "HistoricAverage", "baseline", 2, handles_intermittent=True, why="stationary-noise baseline"
    ),
    ModelSpec(
        "AutoETS",
        "complex",
        3,
        max_season_length=MAX_SEASON_FOR_ETS_ARIMA,
        why="exponential smoothing with automatic trend/season selection",
    ),
    ModelSpec("AutoTheta", "complex", 4, why="robust theta method, good on short series"),
    ModelSpec(
        "AutoARIMA",
        "complex",
        5,
        max_season_length=MAX_SEASON_FOR_ETS_ARIMA,
        why="automatic ARIMA for autocorrelated series",
    ),
)


@dataclass(frozen=True)
class SeriesContext:
    n_obs: int
    season_length: int  # detected primary period, 1 if none
    intermittent: bool


@dataclass(frozen=True)
class Eligibility:
    eligible: bool
    season_length: int  # period the model should be given (may be reduced to 1)
    reason: str = ""


def context_from_profile(profile: ProfileReport) -> SeriesContext:
    return SeriesContext(
        n_obs=profile.stats.n,
        season_length=profile.seasonality.season_length,
        intermittent=profile.intermittency.zero_heavy,
    )


def eligibility(spec: ModelSpec, ctx: SeriesContext) -> Eligibility:
    """Decide whether ``spec`` may run on this series, and with which season length."""
    if ctx.intermittent and not spec.handles_intermittent:
        return Eligibility(False, 1, "intermittent demand: V1 runs baselines only")
    if spec.needs_season and ctx.season_length <= 1:
        return Eligibility(False, 1, "no seasonal period detected")
    season = ctx.season_length
    reason = ""
    if spec.max_season_length is not None and season > spec.max_season_length:
        reason = f"period {season} is too long for {spec.name}; fitted without seasonality"
        season = 1
    return Eligibility(True, season, reason)


def eligible_models(
    ctx: SeriesContext,
) -> tuple[list[tuple[ModelSpec, Eligibility]], list[tuple[ModelSpec, Eligibility]]]:
    """Split the registry into (eligible, skipped) with each model's verdict."""
    run, skipped = [], []
    for spec in REGISTRY:
        verdict = eligibility(spec, ctx)
        (run if verdict.eligible else skipped).append((spec, verdict))
    return run, skipped
