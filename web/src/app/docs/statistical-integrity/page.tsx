import type { Metadata } from "next";

export const metadata: Metadata = { title: "Statistical integrity — /forecast" };

export default function StatisticalIntegrity() {
  return (
    <>
      <h1>Statistical integrity</h1>
      <p>
        Plenty of tools will take a CSV and produce a number. These are the rules{" "}
        <code>/forecast</code> follows, and what separates it from &ldquo;an AI predicts your
        spreadsheet.&rdquo; Each rule is enforced by tests.
      </p>

      <h2>Backtest every model</h2>
      <p>
        A model is trusted only for how it forecast held-out history. How well it fits the past, or
        how plausible its output looks, doesn&rsquo;t count.
      </p>

      <h2>Compare against baselines</h2>
      <p>
        Naive and HistoricAverage always run, and SeasonalNaive runs when a seasonal period is
        found. A more capable model has to beat the best baseline by at least 5% to be selected. If
        it doesn&rsquo;t, the baseline wins and the result says so.
      </p>

      <h2>Expose uncertainty</h2>
      <p>
        Forecasts come with 80% and 95% prediction intervals. The engine also checks how often a
        model&rsquo;s own 80% interval contained the actual value in the backtest. If that was under
        60%, it widens the intervals (never narrows them) and says so. Intervals for each period are
        not added together to make an interval for a total, because errors across periods are
        correlated.
      </p>

      <h2>Don&rsquo;t force unreliable forecasts</h2>
      <p>
        The engine refuses, with a reason, instead of producing a number when the data can&rsquo;t
        support one:
      </p>
      <ul>
        <li>a constant series</li>
        <li>too little history</li>
        <li>irregular sampling</li>
        <li>more than 10% of values missing</li>
        <li>a horizon the history can&rsquo;t validate</li>
        <li>a file that can&rsquo;t be read</li>
      </ul>
      <p>
        A warning fires when the winner beats Naive by less than 10%, so a forecast that is barely
        better than repeating the last value is flagged. There are 33 catalogued warning codes and
        12 refusal codes, each tested. A test fails if a warning is emitted but not catalogued, or
        catalogued but never triggered.
      </p>

      <h2>Distinguish forecasts from observations</h2>
      <p>
        Output files and charts keep observed history and forecast values separate. Claude&rsquo;s
        explanation is expected to say which is which.
      </p>

      <h2>Correlation is not causation</h2>
      <p>
        A forecast extrapolates patterns in the series. It doesn&rsquo;t know why they exist, and it
        doesn&rsquo;t know about a price change, a launch, or a holiday it hasn&rsquo;t seen. V1
        doesn&rsquo;t use external drivers, and the explanation should not attribute a forecast to a
        cause.
      </p>

      <h2>Deterministic calculations</h2>
      <p>
        Every number comes from code: the same dataset and settings produce the same metrics, the
        same winner, and the same forecast.
      </p>

      <h2>Claude does not do the math</h2>
      <p>
        Claude doesn&rsquo;t compute forecasts, compare errors, or choose the model. It interprets
        the engine&rsquo;s output and quotes values from the result files. Its numbers are checked:
        a test requires every number in the engine&rsquo;s text summary to appear in{" "}
        <code>result.json</code>.
      </p>

      <h2>Known limitations in V1</h2>
      <ul>
        <li>One series per run.</li>
        <li>Structural breaks such as a level shift aren&rsquo;t modeled; a warning is raised when recent backtest windows degrade.</li>
        <li>Only one seasonal period is modeled; multiple seasonality is flagged, not handled.</li>
        <li>Intermittent (zero-heavy) demand runs baselines only, with a warning.</li>
        <li>With only a few backtest windows, model selection is noisy. That is why the margin rule exists.</li>
        <li>There is no interval for the sum of a forecast.</li>
      </ul>
    </>
  );
}
