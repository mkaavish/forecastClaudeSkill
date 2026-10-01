import itertools

import pytest

from forecast.schema import RefusedError
from forecast.selection import MARGIN, select_model
from tests.factories import model, summary


def pick(*models, **kw):
    return select_model(summary(*models), **kw)


def test_complex_wins_when_it_clears_the_margin():
    sel = pick(model("Naive", 1.0), model("SeasonalNaive", 0.8), model("AutoETS", 0.6))
    assert (sel.winner, sel.reason, sel.winner_kind) == (
        "AutoETS",
        "beat_baseline_by_margin",
        "complex",
    )
    assert sel.best_baseline == "SeasonalNaive" and sel.improvement_over_baseline == pytest.approx(
        0.25
    )
    assert [r.name for r in sel.ranking] == ["AutoETS", "SeasonalNaive", "Naive"]
    assert [r.rank for r in sel.ranking] == [1, 2, 3]
    assert "25%" in sel.explanation and "AutoETS" in sel.explanation


def test_baseline_wins_when_complex_is_only_slightly_better():
    sel = pick(model("Naive", 1.0), model("AutoETS", 0.97))  # 3% better < 5% margin
    assert (sel.winner, sel.reason) == ("Naive", "baseline_within_margin")
    assert "slightly better" in sel.explanation


def test_baseline_wins_when_complex_is_worse():
    sel = pick(model("Naive", 1.0), model("AutoETS", 1.4), model("AutoARIMA", 1.2))
    assert (sel.winner, sel.reason, sel.best_complex) == ("Naive", "baseline_best", "AutoARIMA")
    assert sel.improvement_over_baseline == pytest.approx(-0.2)


def test_margin_is_strict_at_the_boundary():
    at = select_model(summary(model("Naive", 1.0), model("AutoETS", 0.5)), margin=0.5)
    below = select_model(summary(model("Naive", 1.0), model("AutoETS", 0.4999)), margin=0.5)
    assert at.winner == "Naive" and below.winner == "AutoETS"


def test_default_margin_is_five_percent():
    assert MARGIN == 0.05
    assert pick(model("Naive", 1.0), model("AutoETS", 0.9501)).winner == "Naive"
    assert pick(model("Naive", 1.0), model("AutoETS", 0.9499)).winner == "AutoETS"


def test_best_baseline_is_the_comparison_point():
    # Theta beats Naive by 40% but SeasonalNaive is better still, so Theta must beat *that*.
    sel = pick(model("Naive", 1.0), model("SeasonalNaive", 0.62), model("AutoTheta", 0.6))
    assert sel.winner == "SeasonalNaive" and sel.reason == "baseline_within_margin"


def test_ties_go_to_the_simpler_model():
    assert (
        pick(model("AutoARIMA", 0.5), model("AutoETS", 0.5), model("Naive", 1.0)).winner
        == "AutoETS"
    )
    assert pick(model("SeasonalNaive", 0.7), model("Naive", 0.7)).winner == "Naive"
    assert (
        pick(model("AutoTheta", 0.5), model("AutoETS", 0.5 + 1e-14), model("Naive", 1.0)).winner
        == "AutoETS"
    )


def test_best_complex_is_chosen_among_complex_models_by_score():
    sel = pick(
        model("Naive", 1.0),
        model("AutoETS", 0.55),
        model("AutoARIMA", 0.5),
        model("AutoTheta", 0.7),
    )
    assert sel.winner == "AutoARIMA" and sel.best_complex == "AutoARIMA"


def test_failed_baseline_falls_back_to_the_remaining_baselines():
    sel = pick(
        model("Naive", status="failed"), model("HistoricAverage", 1.0), model("AutoETS", 0.5)
    )
    assert sel.best_baseline == "HistoricAverage" and sel.winner == "AutoETS"


def test_every_baseline_failed_best_complex_wins_with_that_reason():
    sel = pick(model("Naive", status="failed"), model("AutoETS", 0.8), model("AutoARIMA", 0.9))
    assert (sel.winner, sel.reason, sel.best_baseline) == ("AutoETS", "no_baseline_ran", None)


def test_only_baselines_ran():
    sel = pick(
        model("Naive", 1.0),
        model("HistoricAverage", 0.9),
        model("AutoETS", status="skipped", reason="intermittent"),
    )
    assert (sel.winner, sel.reason, sel.best_complex) == (
        "HistoricAverage",
        "only_baselines_ran",
        None,
    )


def test_failed_and_skipped_models_are_never_ranked():
    sel = pick(
        model("Naive", 1.0), model("AutoARIMA", status="failed"), model("AutoETS", status="skipped")
    )
    assert [r.name for r in sel.ranking] == ["Naive"]


def test_no_successful_model_is_a_refusal():
    with pytest.raises(RefusedError) as e:
        pick(model("Naive", status="failed", reason="boom"), model("AutoETS", status="skipped"))
    assert e.value.code == "NO_VALID_MODEL" and e.value.details["failures"] == {"Naive": "boom"}


def test_mae_is_used_when_the_mase_scale_is_undefined():
    sel = select_model(
        summary(model("Naive", None), model("AutoETS", None), scale=None),
    )
    assert sel.metric == "mae"
    assert sel.winner == "Naive"  # identical MAE factory values tie -> the simpler model


def test_a_perfect_baseline_cannot_be_beaten():
    sel = pick(model("Naive", 0.0), model("AutoETS", 0.0))
    assert sel.winner == "Naive" and sel.improvement_over_baseline is None


def test_selection_ignores_the_order_models_are_listed_in():
    models = [
        model("Naive", 1.0),
        model("SeasonalNaive", 0.8),
        model("AutoETS", 0.6),
        model("AutoARIMA", 0.6),
        model("AutoTheta", 0.7),
    ]
    results = {
        select_model(summary(*perm)).model_dump_json() for perm in itertools.permutations(models)
    }
    assert len(results) == 1


def test_selection_ignores_everything_but_the_scores():
    a = pick(
        model("Naive", 1.0, coverage_80=0.1, width=99.0), model("AutoETS", 0.5, coverage_80=0.99)
    )
    b = pick(model("Naive", 1.0), model("AutoETS", 0.5))
    assert a.winner == b.winner == "AutoETS" and a.ranking == b.ranking
