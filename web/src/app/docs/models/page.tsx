import type { Metadata } from "next";

export const metadata: Metadata = { title: "Models & backtesting — /forecast" };

export default function Models() {
  return (
    <>
      <h1>Models &amp; backtesting</h1>
      <p>
        Six models compete on every run: three baselines and three more capable ones. A fixed rule
        chooses between them using held-out history.
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
              <td>Repeats the last observed value. The minimum bar any model has to clear. Baseline.</td>
            </tr>
            <tr>
              <td><code>SeasonalNaive</code></td>
              <td>
                Repeats the value from the same point in the last cycle (the same weekday last
                week, for daily data). Runs only when a seasonal period is found. Baseline.
              </td>
            </tr>
            <tr>
              <td><code>HistoricAverage</code></td>
              <td>
                Forecasts the mean of all history. The right baseline for noise around a constant.
                Baseline.
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
              <td><code>AutoTheta</code></td>
              <td>Robust and cheap, and good on short series.</td>
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
        On zero-heavy data (at least 30% zeros) only the baselines run, because the more capable
        models aren&rsquo;t built for intermittent demand.
      </p>

      <h2>Rolling-origin backtesting</h2>
      <p>
        A model that fits the past well can still forecast badly. To measure forecasting skill, the
        engine hides the end of the history, forecasts it, and compares with what happened. It
        repeats this from several cut-off points, each time training on everything before the
        cut-off and forecasting the next stretch.
      </p>
      <ul>
        <li>
          <strong>3 to 5 windows</strong>, each as long as the forecast horizon, with growing
          training sets. A 30-day forecast is scored on 30-day-ahead errors.
        </li>
        <li>
          <strong>Shortened horizon.</strong> If the history is too short for that, the test
          horizon is shortened and the result carries a warning.
        </li>
        <li>
          <strong>Refusal.</strong> Below a floor the run refuses and states the longest horizon
          the history can support.
        </li>
      </ul>
      <p>
        Scoring over several windows is less luck-dependent than a single train/test split.
      </p>

      <h2>Metrics</h2>
      <p>
        Models are ranked by <strong>MASE</strong>, pooled over all backtest windows. MAE, RMSE and
        sMAPE are reported alongside it.
      </p>
      <ul>
        <li>
          <strong>MASE</strong>: a model&rsquo;s average error divided by the training-data error of
          a seasonal-naive forecast. Below 1 beats that yardstick, though multi-step forecasts
          commonly score above 1. It is scale-free and safe when values hit zero.
        </li>
        <li>
          <strong>MAE</strong>: mean absolute error. The average miss, in the units of your data.
        </li>
        <li>
          <strong>RMSE</strong>: root mean squared error. Like MAE but punishes large misses more.
        </li>
        <li>
          <strong>sMAPE</strong>: symmetric percentage error, on a 0&ndash;200% scale. Scale-free,
          but unstable when values are near zero.
        </li>
      </ul>

      <h2>Deterministic model selection</h2>
      <p>The winner comes from a fixed rule applied to the backtest errors, not from Claude:</p>
      <ol>
        <li>Score every eligible model on the same windows.</li>
        <li>Find the best baseline: Naive, SeasonalNaive or HistoricAverage.</li>
        <li>
          A more capable model wins only if it beats that baseline by at least 5%. Otherwise the
          baseline wins.
        </li>
        <li>Ties go to the simpler model.</li>
      </ol>
      <p>The same data and settings give the same winner, and the result records why it won.</p>

      <h2>Intervals</h2>
      <p>
        Forecasts carry 80% and 95% prediction intervals. If a model&rsquo;s own 80% interval
        covered under 60% of the backtest actuals, the intervals are widened (never narrowed) and
        the result says so.
      </p>

      <h2>Why baselines matter</h2>
      <p>
        With only a handful of backtest windows, small error differences are mostly noise. The
        margin exists to avoid claiming structure in noise. In tests on noise and random walks,
        with no margin a more capable model &ldquo;won&rdquo; 72% of the time. With a 5% margin it
        won 9% of the time.
      </p>
      <p>
        The margin does not improve accuracy, and we don&rsquo;t claim it does. A benchmark on 260
        series, scored on held-out data, found margins from 0% to 10% statistically
        indistinguishable on accuracy. What did matter was having the capable models at all:
        never using them gave about 40% more error. If a simple baseline performs best, the
        baseline wins, and the result says so.
      </p>
    </>
  );
}
