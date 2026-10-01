# Example datasets

All synthetic and seeded (`python examples/make_examples.py` regenerates them); no external data.

| File | Situation | What to expect |
|---|---|---|
| `retail_sales.csv` | Daily sales, weekend peaks, steady growth, a few promotion spikes | Weekly seasonality and a positive trend are found; a complex model (AutoETS) beats the seasonal baseline. |
| `saas_revenue.csv` | Monthly recurring revenue with compounding growth, 60 months | Short history: few backtest windows, a poor-backtest warning, and recalibrated intervals. |
| `website_traffic.csv` | Daily visits: wandering level, weak weekly pattern, viral spikes | Hard to forecast: a baseline wins, with warnings about poor backtest accuracy and very wide intervals. |
| `inventory_demand.csv` | Slow-moving item, ~70% zero days | Intermittent demand: baselines only, with a warning. |
| `multi_store_sales.csv` | `date,store,product,units_sold,inventory,price` | Ambiguous: `forecast` asks which series. Try `--where store=North --where product=Widget` or `--agg sum`. |

```bash
forecast examples/retail_sales.csv --horizon 30
forecast examples/multi_store_sales.csv --agg sum
```
