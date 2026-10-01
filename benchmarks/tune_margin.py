"""Choose the selection margin from held-out forecast error, not from taste.

For many synthetic series with known structure we do exactly what a user's run does on the
first n points: backtest, then take the best baseline and the best complex model. We then
refit both on all n points and score them on the NEXT h points, which no part of the
procedure has seen. For a margin d the rule picks the complex model iff its backtest score
beats the baseline's by at least d, so one pass over the data prices every candidate d.

    python benchmarks/tune_margin.py            # run and save benchmarks/margin_runs.json
    python benchmarks/tune_margin.py --analyze  # tabulate from the saved runs
"""

from __future__ import annotations

import json
import sys
import tempfile
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = Path(__file__).with_name("margin_runs.json")
H, SEEDS = 14, 20
MARGINS = [0.0, 0.02, 0.03, 0.05, 0.075, 0.10, 0.15, 0.25]


def frame(y: np.ndarray, freq: str = "D") -> pd.DataFrame:
    return pd.DataFrame(
        {"date": pd.date_range("2022-01-01", periods=len(y), freq=freq), "value": y}
    )


def gen_white(n, rng):
    return 50 + rng.normal(0, 5, n)


def gen_walk(n, rng):
    return 100 + np.cumsum(rng.normal(0, 1, n))


def gen_ar1(n, rng):
    y = np.zeros(n)
    for t in range(1, n):
        y[t] = 0.7 * y[t - 1] + rng.normal(0, 1)
    return 50 + y


def gen_trend_weak(n, rng):
    return 100 + 0.15 * np.arange(n) + rng.normal(0, 5, n)


def gen_trend_seasonal(n, rng):
    t = np.arange(n)
    return 100 + 0.5 * t + 15 * np.sin(2 * np.pi * t / 7) + rng.normal(0, 2, n)


def gen_seasonal_weak(n, rng):
    t = np.arange(n)
    return 200 + 3 * np.sin(2 * np.pi * t / 7) + rng.normal(0, 5, n)


def gen_seasonal_strong(n, rng):
    t = np.arange(n)
    return 200 + 20 * np.sin(2 * np.pi * t / 7) + rng.normal(0, 2, n)


def gen_level_shift(n, rng):
    return np.where(np.arange(n + H) < int(0.7 * (n + H)), 100.0, 130.0)[:n] + rng.normal(0, 3, n)


def gen_seasonal_walk(n, rng):
    t = np.arange(n)
    return 100 + np.cumsum(rng.normal(0, 1, n)) + 10 * np.sin(2 * np.pi * t / 7)


def gen_damped(n, rng):
    t = np.arange(n)
    return 100 + 40 * (1 - 0.97**t) + rng.normal(0, 3, n)


SCENARIOS = {  # name -> (generator, n_train, truth: does the series contain learnable structure?)
    "white noise": (gen_white, 220, "null"),
    "white noise (short)": (gen_white, 80, "null"),
    "random walk": (gen_walk, 220, "null"),
    "random walk (short)": (gen_walk, 80, "null"),
    "AR(1) stationary": (gen_ar1, 220, "weak"),
    "weak trend": (gen_trend_weak, 220, "weak"),
    "weak seasonality": (gen_seasonal_weak, 220, "weak"),
    "level shift": (gen_level_shift, 220, "weak"),
    "damped growth": (gen_damped, 220, "weak"),
    "strong seasonality": (gen_seasonal_strong, 220, "signal"),
    "trend + seasonality": (gen_trend_seasonal, 220, "signal"),
    "trend + seasonality (short)": (gen_trend_seasonal, 80, "signal"),
    "seasonal + random walk": (gen_seasonal_walk, 220, "signal"),
}


def holdout_mae(data, freq, spec, season, future):
    from statsforecast import StatsForecast

    from forecast.models import build_model

    sf_in = pd.DataFrame({"unique_id": "s", "ds": data["ds"], "y": data["y"]})
    out = StatsForecast(models=[build_model(spec, season)], freq=freq, n_jobs=1).forecast(
        h=len(future), df=sf_in
    )
    return float(np.mean(np.abs(out[spec.name].to_numpy() - future)))


def plan_or_none(ctx):
    from forecast.backtest import plan_backtest
    from forecast.schema import RefusedError

    try:
        return plan_backtest(ctx.n_obs, H, ctx.season_length)
    except RefusedError:
        return None


def collect() -> None:
    warnings.simplefilter("ignore")
    from forecast.backtest import run_backtest
    from forecast.loading import load_series
    from forecast.models import REGISTRY, context_from_profile, eligible_models
    from forecast.profile import profile_series

    spec_by_name = {s.name: s for s in REGISTRY}
    runs = []
    with tempfile.TemporaryDirectory() as tmp:
        for name, (gen, n, truth) in SCENARIOS.items():
            for seed in range(SEEDS):
                rng = np.random.default_rng(1000 * seed + n)
                y = gen(n + H, rng)
                df = frame(y)
                path = Path(tmp) / "d.csv"
                df.iloc[:n].to_csv(path, index=False)
                loaded = load_series(path)
                profile = profile_series(loaded)
                if profile.constant:
                    continue
                ctx = context_from_profile(profile)
                plan = plan_or_none(ctx)
                if plan is None:
                    continue  # refused runs are not part of the comparison
                run, skipped = eligible_models(ctx)
                summary = run_backtest(loaded.data, loaded.freq, plan, run, skipped).summary
                ok = [m for m in summary.models if m.status == "ok"]
                score = lambda m: m.metrics.mase if m.metrics.mase is not None else m.metrics.mae
                base = [m for m in ok if m.kind == "baseline"]
                cmpx = [m for m in ok if m.kind == "complex"]
                if not base or not cmpx:
                    continue
                b, c = min(base, key=score), min(cmpx, key=score)
                future = y[n:]
                runs.append({
                    "scenario": name, "truth": truth, "seed": seed, "baseline": b.name, "complex": c.name,
                    "improvement": 1 - score(c) / score(b) if score(b) > 0 else 0.0,
                    "mae_baseline": holdout_mae(loaded.data, loaded.freq, spec_by_name[b.name], b.season_length, future),
                    "mae_complex": holdout_mae(loaded.data, loaded.freq, spec_by_name[c.name], c.season_length, future),
                })  # fmt: skip
            print(f"done {name}", flush=True)
    OUT.write_text(json.dumps(runs))


def analyze() -> None:
    runs = pd.DataFrame(json.loads(OUT.read_text()))
    runs["best"] = runs[["mae_baseline", "mae_complex"]].min(axis=1)
    print(f"{len(runs)} runs, {runs['scenario'].nunique()} scenarios\n")

    def regret(df, margin):
        picks_complex = df["improvement"] >= margin
        chosen = np.where(picks_complex, df["mae_complex"], df["mae_baseline"])
        return float(
            np.mean(chosen / df["best"] - 1)
        )  # excess held-out error over the better of the two

    header = (
        f"{'margin':>7} {'promoted':>9} "
        + " ".join(f"{t:>8}" for t in ("null", "weak", "signal"))
        + f" {'ALL regret':>11}"
    )
    print(
        "regret = mean excess held-out MAE over the better model; promoted = share choosing complex"
    )
    print(header)
    for m in MARGINS:
        promoted = (runs["improvement"] >= m).mean()
        by_truth = [regret(runs[runs["truth"] == t], m) for t in ("null", "weak", "signal")]
        print(
            f"{m:>7.3f} {promoted:>9.0%} "
            + " ".join(f"{r:>8.1%}" for r in by_truth)
            + f" {regret(runs, m):>11.2%}"
        )
    print("\nper-scenario promotion rate at each margin:")
    print(f"{'':28s}" + "".join(f"{m:>7.3f}" for m in MARGINS))
    for name, g in runs.groupby("scenario", sort=False):
        print(f"{name:28s}" + "".join(f"{(g['improvement'] >= m).mean():>7.0%}" for m in MARGINS))
    print(
        "\nalways baseline:",
        f"{regret(runs, 9):.2%}",
        "| always complex:",
        f"{regret(runs, -9):.2%}",
    )


if __name__ == "__main__":
    if "--analyze" in sys.argv:
        analyze()
    else:
        collect()
        analyze()
