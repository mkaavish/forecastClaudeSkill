"""Regenerate the demo datasets (seeded, synthetic, no external data).

    python examples/make_examples.py

Each file demonstrates a different forecasting situation; see examples/README.md.
"""

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).parent


def retail_sales() -> pd.DataFrame:
    """Daily sales: weekend peaks, steady growth, a few promotion spikes."""
    rng = np.random.default_rng(101)
    dates = pd.date_range("2024-01-01", "2025-12-31", freq="D")
    t = np.arange(len(dates))
    weekly = np.array([0.92, 0.88, 0.90, 0.95, 1.05, 1.22, 1.08])[dates.dayofweek]
    base = (9000 + 9 * t) * weekly
    sales = base * rng.normal(1.0, 0.04, len(t))
    sales[rng.choice(len(t), 4, replace=False)] *= 1.6  # promotions
    return pd.DataFrame({"date": dates, "sales": sales.round(0).astype(int)})


def saas_revenue() -> pd.DataFrame:
    """Monthly recurring revenue: compounding growth with mild noise."""
    rng = np.random.default_rng(202)
    months = pd.date_range("2021-01-01", periods=60, freq="MS")
    mrr = 40000 * 1.028 ** np.arange(60) * rng.normal(1.0, 0.012, 60)
    return pd.DataFrame({"month": months, "mrr": mrr.round(0).astype(int)})


def website_traffic() -> pd.DataFrame:
    """Daily visits: a wandering level, weak weekly pattern, occasional viral spikes. Hard to forecast."""
    rng = np.random.default_rng(303)
    dates = pd.date_range("2025-01-01", periods=300, freq="D")
    level = 5000 + np.cumsum(rng.normal(0, 90, len(dates)))
    weekly = np.array([1.04, 1.06, 1.05, 1.03, 0.98, 0.9, 0.94])[dates.dayofweek]
    visits = level * weekly * rng.normal(1.0, 0.08, len(dates))
    visits[rng.choice(len(dates), 3, replace=False)] *= 2.8
    return pd.DataFrame({"date": dates, "visits": visits.round(0).astype(int)})


def inventory_demand() -> pd.DataFrame:
    """Daily units for a slow-moving item: roughly 70% of days have no demand at all."""
    rng = np.random.default_rng(404)
    dates = pd.date_range("2025-01-01", periods=300, freq="D")
    units = np.where(rng.random(len(dates)) < 0.7, 0, rng.poisson(5, len(dates)) + 1)
    return pd.DataFrame({"date": dates, "units": units})


def multi_store_sales() -> pd.DataFrame:
    """Several stores and products: which series to forecast is a genuine question."""
    rng = np.random.default_rng(505)
    dates = pd.date_range("2025-01-01", periods=120, freq="D")
    rows = []
    for store, s_scale in (("North", 1.0), ("South", 1.4)):
        for product, p_scale in (("Widget", 1.0), ("Gadget", 0.6)):
            base = 50 * s_scale * p_scale
            for i, d in enumerate(dates):
                units = base * (1 + 0.15 * np.sin(2 * np.pi * i / 7)) * rng.normal(1, 0.06) + 0.1 * i
                rows.append((d, store, product, int(round(units)), int(rng.integers(200, 400)), 9.99 if product == "Widget" else 24.5))
    return pd.DataFrame(rows, columns=["date", "store", "product", "units_sold", "inventory", "price"])


if __name__ == "__main__":
    for name, frame in {
        "retail_sales": retail_sales(),
        "saas_revenue": saas_revenue(),
        "website_traffic": website_traffic(),
        "inventory_demand": inventory_demand(),
        "multi_store_sales": multi_store_sales(),
    }.items():
        frame.to_csv(OUT / f"{name}.csv", index=False, date_format="%Y-%m-%d")
        print(f"wrote {name}.csv ({len(frame)} rows)")
