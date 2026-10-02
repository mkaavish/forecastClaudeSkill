import type { Metadata } from "next";
import { CodeBlock } from "@/components/code-block";

export const metadata: Metadata = { title: "Outputs — /forecast" };

export default function Outputs() {
  return (
    <>
      <h1>Outputs</h1>
      <p>
        Each run writes its files to an output folder, <code>./forecast-output/&lt;name&gt;/</code>{" "}
        by default. Change it with <code>--output</code>.
      </p>
      <CodeBlock>{`forecast-output/sales/
├── profile.json
├── result.json
├── backtest.csv
├── forecast.csv
└── forecast.png`}</CodeBlock>

      <h2>forecast.csv</h2>
      <p>One row per forecast period, with exactly these columns:</p>
      <CodeBlock>{`series, ds, forecast, lo_80, hi_80, lo_95, hi_95, model`}</CodeBlock>
      <p>
        Point forecast, 80% and 95% interval bounds, and the model that produced them. For targets
        that can&rsquo;t be negative, lower bounds are clipped at zero.
      </p>

      <h2>forecast.png</h2>
      <p>
        A chart of the history, a line marking where the forecast starts, the forecast, and shaded
        interval bands, so observed and forecast values are visually distinct. If the chart fails,
        the forecast and the other files are still written, with a <code>PLOT_FAILED</code>{" "}
        warning.
      </p>

      <h2>result.json</h2>
      <p>The machine-readable result of a run. It contains:</p>
      <ul>
        <li>the input and its profile</li>
        <li>backtest scores for every model</li>
        <li>the selection, with the reason the winner won</li>
        <li>
          the forecast, including the first and last periods with their intervals and a number for
          how fast interval width grows
        </li>
        <li>the intervals, native or calibrated</li>
        <li>a de-duplicated list of warnings</li>
        <li>artifact paths and run metadata</li>
      </ul>
      <p>
        Claude reads this file to write its explanation. Every JSON file carries a{" "}
        <code>schema_version</code>, and the JSON Schemas are in the repository&rsquo;s{" "}
        <code>schemas/</code> folder.
      </p>

      <h2>profile.json</h2>
      <p>
        What the engine learned about the dataset: detected columns, frequency, missing timestamps,
        duplicates, outliers, trend and seasonality, and any ambiguities that need an answer.
      </p>

      <h2>backtest.csv</h2>
      <p>Errors per window and model, so you can check the selection yourself.</p>

      <h2>What isn&rsquo;t written</h2>
      <p>
        There is no <code>metrics.json</code> or <code>report.md</code>. Metrics live inside{" "}
        <code>result.json</code>, and the written analysis is Claude&rsquo;s reply rather than a
        file.
      </p>
    </>
  );
}
