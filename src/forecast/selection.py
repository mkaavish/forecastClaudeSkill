"""Deterministic model selection.

The rule, in full:

1. Score every model that finished the backtest on pooled MASE (MAE if the MASE scale is
   undefined). Lower is better.
2. Find the best baseline (Naive, SeasonalNaive, HistoricAverage) and the best complex model.
3. A complex model wins only if it beats the best baseline by at least ``MARGIN``
   (strictly: ``complex < baseline * (1 - MARGIN)``). Otherwise the baseline wins.
4. Ties, in either group, go to the simpler model (``ModelSpec.simplicity``).

No input other than the backtest numbers can change the outcome, and the order models are
listed in does not matter.
"""

from __future__ import annotations

from forecast.models import REGISTRY
from forecast.schema import BacktestSummary, ModelBacktest, RankedModel, RefusedError, Selection

# A complex model must improve on the best baseline by this fraction. Measured on 20 seeds
# per series type (Phase 5): pure noise was never promoted at 3%; random walks were promoted
# 30% of the time at 3%, 15% at 5%, 5% at 10%; every series with real signal improved by at
# least 22%, so 5% costs nothing there. Re-tuned on a wider benchmark in the release phase.
MARGIN = 0.05

_SIMPLICITY = {spec.name: spec.simplicity for spec in REGISTRY}


def _score(model: ModelBacktest, metric: str) -> float:
    m = model.metrics
    return m.mase if metric == "mase" else m.mae  # type: ignore[return-value]


def _best(models: list[ModelBacktest], metric: str) -> ModelBacktest | None:
    if not models:
        return None
    # Rounding makes float noise irrelevant: scores equal to 12 places are ties.
    return min(
        models, key=lambda m: (round(_score(m, metric), 12), _SIMPLICITY.get(m.name, 99), m.name)
    )


def select_model(summary: BacktestSummary, margin: float = MARGIN) -> Selection:
    ok = [m for m in summary.models if m.status == "ok" and m.metrics is not None]
    if not ok:
        raise RefusedError(
            "NO_VALID_MODEL",
            "No model completed the backtest, so no forecast can be justified.",
            failures={m.name: m.reason for m in summary.models if m.status == "failed"},
        )
    metric = "mase" if all(m.metrics.mase is not None for m in ok) else "mae"
    ranked = sorted(
        ok, key=lambda m: (round(_score(m, metric), 12), _SIMPLICITY.get(m.name, 99), m.name)
    )
    ranking = [
        RankedModel(name=m.name, kind=m.kind, score=_score(m, metric), rank=i + 1)
        for i, m in enumerate(ranked)
    ]

    baseline = _best([m for m in ok if m.kind == "baseline"], metric)
    complex_ = _best([m for m in ok if m.kind == "complex"], metric)
    improvement = None
    if baseline is not None and complex_ is not None:
        b, c = _score(baseline, metric), _score(complex_, metric)
        improvement = (1 - c / b) if b > 0 else None
        if c < b * (1 - margin):
            winner, reason = complex_, "beat_baseline_by_margin"
        elif c < b:
            winner, reason = baseline, "baseline_within_margin"
        else:
            winner, reason = baseline, "baseline_best"
    elif baseline is not None:
        winner, reason = baseline, "only_baselines_ran"
    else:
        winner, reason = complex_, "no_baseline_ran"  # type: ignore[assignment]

    return Selection(
        winner=winner.name,
        winner_kind=winner.kind,
        reason=reason,  # type: ignore[arg-type]
        metric=metric,  # type: ignore[arg-type]
        required_margin=margin,
        best_baseline=baseline.name if baseline else None,
        best_complex=complex_.name if complex_ else None,
        improvement_over_baseline=improvement,
        ranking=ranking,
        explanation=_explain(
            winner, baseline, complex_, reason, metric, margin, improvement, summary
        ),
    )


def _explain(winner, baseline, complex_, reason, metric, margin, improvement, summary) -> str:
    label = metric.upper()
    score = _score(winner, metric)
    n_win = summary.plan.n_windows
    if reason == "beat_baseline_by_margin":
        return (
            f"{winner.name} had the lowest {label} ({score:.3g}) over {n_win} rolling backtest windows and beat "
            f"the best baseline, {baseline.name} ({_score(baseline, metric):.3g}), by {improvement:.0%}, "
            f"more than the {margin:.0%} a complex model must clear."
        )
    if reason == "baseline_within_margin":
        return (
            f"{complex_.name} scored slightly better than {winner.name} but by only {improvement:.1%}, "
            f"less than the {margin:.0%} a complex model must clear, so the simpler baseline "
            f"{winner.name} ({label} {score:.3g}) was selected."
        )
    if reason == "baseline_best":
        return (
            f"No complex model beat the baseline: {winner.name} ({label} {score:.3g}) scored at least as well "
            f"as the best complex model, {complex_.name} ({_score(complex_, metric):.3g})."
        )
    if reason == "only_baselines_ran":
        return f"Only baseline models ran; {winner.name} had the lowest {label} ({score:.3g})."
    return f"Every baseline failed; {winner.name} had the lowest {label} ({score:.3g}) of the remaining models."
