import type { Metadata } from "next";
import { StatusBadge } from "@/components/status-badge";

export const metadata: Metadata = { title: "Models & backtesting — /forecast" };

export default function Models() {
  return (
    <>
      <h1>Models &amp; backtesting</h1>
      <p>
        <StatusBadge status="planned" /> Everything on this page describes V1 as designed. The
        details, especially the selection thresholds, may change as the engine is built and
        benchmarked.
      </p>

      <h2>Models</h2>
      <p>The engine uses the open-source StatsForecast library.</p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Model</th>
              <th>What it does</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><code>Naive</code></td>
              <td>Repeats the last observed value. The minimum bar any model has to clear.</td>
            </tr>
            <tr>
              <td><code>SeasonalNaive</code></td>
              <td>
                Repeats the value from the same point in the last cycle (the same weekday last
                week, for daily data). Used when the data has a seasonal period.
              </td>
            </tr>
            <tr>
              <td><code>AutoETS</code></td>
              <td>
                Exponential smoothing. Automatically chooses how to model level, trend, and
                seasonality. A strong default for trending or seasonal series.
              </td>
            </tr>
            <tr>
              <td><code>AutoARIMA</code></td>
              <td>
                Automatically fits an ARIMA model. Can capture autocorrelation that smoothing
                models miss.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p>
        The design also lists two extra candidates, a historic average and AutoTheta, that stay in
        only if benchmarks show they earn it.
      </p>

      <h2>Rolling-origin backtesting</h2>
      <p>
        A model that fits the past well can still forecast badly. To measure forecasting skill, the
        engine hides the end of the history, forecasts it, and compares with what happened. It
        repeats this from several cut-off points, each time training on everything before the
        cut-off and forecasting the next horizon-length stretch.
      </p>
      <p>
        The backtest horizon matches the forecast horizon, so a 30-day forecast is scored on
        30-day-ahead errors. Scoring over several windows is less luck-dependent than a single
        train/test split.
      </p>

      <h2>Metrics</h2>
      <ul>
        <li>
          <strong>MAE</strong>: mean absolute error. The average miss, in the units of your data.
        </li>
        <li>
          <strong>RMSE</strong>: root mean squared error. Like MAE but punishes large misses more.
        </li>
        <li>
          <strong>sMAPE</strong>: symmetric percentage error. Scale-free, but unstable when values
          are near zero.
        </li>
      </ul>
      <p>
        Because sMAPE misbehaves on zero-heavy data, the plan is to rank models with MASE (error
        relative to a seasonal-naive forecast; below 1 beats that baseline) and report MAE, RMSE, and
        sMAPE alongside it. This choice is not final.
      </p>

      <h2>Deterministic model selection</h2>
      <p>The winner comes from a fixed rule applied to the backtest errors, not from Claude:</p>
      <ol>
        <li>Score every eligible model on the same windows.</li>
        <li>Find the best baseline (Naive or Seasonal Naive).</li>
        <li>
          A more complex model wins only if it beats that baseline by a margin (3% is the starting
          value, to be tuned on synthetic data). Otherwise the baseline wins.
        </li>
        <li>Ties go to the simpler model.</li>
      </ol>
      <p>
        The same data and settings give the same winner, and the result records why it won.
      </p>

      <h2>Why baselines matter</h2>
      <p>
        With only a handful of backtest windows, small error differences are mostly noise. Without a
        margin, a complicated model would win by chance, and you&rsquo;d get a forecast that looks
        sophisticated and is no better than repeating last week. Requiring a clear win keeps the
        engine honest: if a simple baseline performs best, the baseline wins, and the result says so.
      </p>
    </>
  );
}
