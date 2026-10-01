import type { Metadata } from "next";
import { StatusBadge } from "@/components/status-badge";

export const metadata: Metadata = { title: "Statistical integrity — /forecast" };

export default function StatisticalIntegrity() {
  return (
    <>
      <h1>Statistical integrity</h1>
      <p>
        Plenty of tools will take a CSV and produce a number. These are the rules{" "}
        <code>/forecast</code> is designed around, and what separates it from &ldquo;an AI predicts
        your spreadsheet.&rdquo; <StatusBadge status="planned" /> They are design commitments for V1;
        the engine that enforces them is still being built.
      </p>

      <h2>Backtest every model</h2>
      <p>
        A model is trusted only for how it forecast held-out history. How well it fits the past, or
        how plausible its output looks, doesn&rsquo;t count.
      </p>

      <h2>Compare against baselines</h2>
      <p>
        Naive and Seasonal Naive always run. A more complex model has to beat the best baseline by a
        margin to be selected. If it doesn&rsquo;t, the baseline wins and the result says so.
      </p>

      <h2>Expose uncertainty</h2>
      <p>
        Forecasts come with 80% and 95% prediction intervals. The engine also checks how often the
        80% interval would have contained the actual value in the backtest, and warns if the
        intervals look too narrow. Intervals for a period are not added together to make an interval
        for a total, because errors across periods are correlated.
      </p>

      <h2>Don&rsquo;t force unreliable forecasts</h2>
      <p>
        If the history is too short, the series is constant, or too much data is missing, the engine
        refuses with a reason instead of producing a number. If no model beats a naive forecast, or
        backtest errors swing widely between windows, the result carries a warning.
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
        the engine&rsquo;s output and is expected to quote values from the result files and add no
        figures of its own.
      </p>

      <h2>Known limitations in V1</h2>
      <ul>
        <li>One series per run.</li>
        <li>Structural breaks such as a level shift aren&rsquo;t modeled; a warning is raised when recent backtest windows degrade.</li>
        <li>Only one seasonal period is modeled; multiple seasonality is flagged, not handled.</li>
        <li>Intermittent (zero-heavy) demand runs baselines only, with a warning.</li>
        <li>With only a few backtest windows, model selection is noisy. That is why the margin rule exists.</li>
      </ul>
    </>
  );
}
