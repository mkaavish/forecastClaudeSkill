import pytest

from forecast.diagnostics import check_forecastable
from forecast.loading import load_series
from forecast.models import (
    REGISTRY,
    SeriesContext,
    context_from_profile,
    eligibility,
    eligible_models,
)
from forecast.profile import profile_series
from forecast.schema import RefusedError
from tests import synthetic

SPEC = {s.name: s for s in REGISTRY}


def names(pairs):
    return [spec.name for spec, _ in pairs]


def test_registry_has_baselines_and_unique_simplicity_ranks():
    assert {s.name for s in REGISTRY if s.kind == "baseline"} == {
        "Naive",
        "SeasonalNaive",
        "HistoricAverage",
    }
    ranks = [s.simplicity for s in REGISTRY]
    assert len(set(ranks)) == len(ranks)
    # every complex model is more complex than every baseline (tie-break order)
    assert max(s.simplicity for s in REGISTRY if s.kind == "baseline") < min(
        s.simplicity for s in REGISTRY if s.kind == "complex"
    )
    assert all(s.why for s in REGISTRY)  # every model states why it exists


def test_seasonal_series_runs_everything():
    run, skipped = eligible_models(SeriesContext(n_obs=300, season_length=7, intermittent=False))
    assert set(names(run)) == set(SPEC) and skipped == []


def test_non_seasonal_series_skips_only_seasonal_naive():
    run, skipped = eligible_models(SeriesContext(n_obs=300, season_length=1, intermittent=False))
    assert names(skipped) == ["SeasonalNaive"] and "no seasonal period" in skipped[0][1].reason
    assert "Naive" in names(run) and "HistoricAverage" in names(run)


def test_intermittent_series_runs_baselines_only():
    run, skipped = eligible_models(SeriesContext(n_obs=300, season_length=7, intermittent=True))
    assert set(names(run)) == {"Naive", "SeasonalNaive", "HistoricAverage"}
    assert set(names(skipped)) == {"AutoETS", "AutoTheta", "AutoARIMA"}
    assert all("intermittent" in v.reason for _, v in skipped)


def test_ets_keeps_long_periods_but_arima_and_ets_drop_very_long_ones():
    hourly_week = SeriesContext(n_obs=2000, season_length=168, intermittent=False)
    expected = {"AutoETS": 168, "AutoARIMA": 1, "AutoTheta": 168, "SeasonalNaive": 168}
    for name, season in expected.items():
        verdict = eligibility(SPEC[name], hourly_week)
        assert verdict.eligible and verdict.season_length == season, name
    assert "too long" in eligibility(SPEC["AutoARIMA"], hourly_week).reason
    daily_year = SeriesContext(n_obs=2000, season_length=365, intermittent=False)
    assert eligibility(SPEC["AutoETS"], daily_year).season_length == 1
    assert eligibility(SPEC["AutoTheta"], daily_year).season_length == 365


def test_period_at_the_cap_is_kept():
    assert eligibility(SPEC["AutoARIMA"], SeriesContext(500, 24, False)).season_length == 24
    assert eligibility(SPEC["AutoETS"], SeriesContext(500, 168, False)).season_length == 168


def test_seasonal_arima_is_dropped_when_too_costly():
    cheap = eligibility(SPEC["AutoARIMA"], SeriesContext(1000, 24, False))  # 24k
    costly = eligibility(SPEC["AutoARIMA"], SeriesContext(5000, 24, False))  # 120k
    assert cheap.season_length == 24 and costly.season_length == 1 and "too slow" in costly.reason
    # non-seasonal ARIMA is never limited by cost
    assert eligibility(SPEC["AutoARIMA"], SeriesContext(100_000, 1, False)).season_length == 1


def test_context_from_profile(tmp_path):
    p = tmp_path / "d.csv"
    synthetic.zero_heavy().to_csv(p, index=False)
    ctx = context_from_profile(profile_series(load_series(p)))
    assert ctx.intermittent and ctx.n_obs == 200


def test_constant_series_is_refused(tmp_path):
    p = tmp_path / "c.csv"
    synthetic.constant().to_csv(p, index=False)
    with pytest.raises(RefusedError) as e:
        check_forecastable(profile_series(load_series(p)))
    assert e.value.code == "CONSTANT_SERIES" and e.value.details["value"] == 5.0


def test_ordinary_series_passes_forecastable_check(tmp_path):
    for df in (synthetic.white_noise(), synthetic.zero_heavy(), synthetic.trend_seasonality()):
        p = tmp_path / "d.csv"
        df.to_csv(p, index=False)
        check_forecastable(profile_series(load_series(p)))  # must not raise
