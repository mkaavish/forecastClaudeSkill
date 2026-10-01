import type { Metadata } from "next";
import { Callout } from "@/components/callout";
import { CodeBlock } from "@/components/code-block";
import { StatusBadge } from "@/components/status-badge";

export const metadata: Metadata = { title: "Outputs — /forecast" };

export default function Outputs() {
  return (
    <>
      <h1>Outputs</h1>
      <Callout title="Planned, not implemented">
        <p>
          <StatusBadge status="planned" /> No output files are produced yet. This is the V1 design;
          names and columns may change.
        </p>
      </Callout>
      <p>
        Each run writes its files to an output folder, <code>./forecast-output/&lt;name&gt;/</code>{" "}
        by default.
      </p>
      <CodeBlock>{`forecast-output/sales/
├── profile.json
├── result.json
├── backtest.csv
├── forecast.csv
└── forecast.png`}</CodeBlock>

      <h2>forecast.csv</h2>
      <p>
        One row per forecast period: the date, the point forecast, 80% and 95% prediction interval
        bounds, and the model that produced it. For targets that can&rsquo;t be negative, lower
        bounds are clipped at zero.
      </p>

      <h2>forecast.png</h2>
      <p>
        A chart of the history, a line marking where the forecast starts, the forecast, and shaded
        interval bands, so observed and forecast values are visually distinct.
      </p>

      <h2>result.json</h2>
      <p>
        The machine-readable result of a run: input details, backtest scores for every model
        (MAE, RMSE, sMAPE, and the ranking metric), the selected model and the reason it won,
        forecast totals, interval coverage measured in the backtest, and warnings with stable
        codes. Claude reads this file to write its explanation. Every JSON file carries a{" "}
        <code>schema_version</code>.
      </p>

      <h2>profile.json</h2>
      <p>
        What the engine learned about the dataset: detected columns, frequency, missing timestamps,
        duplicates, outliers, trend and seasonality, and any ambiguities that need an answer.
      </p>

      <h2>backtest.csv</h2>
      <p>Errors per window and model, so you can check the selection yourself.</p>

      <h2>A note on report files</h2>
      <p>
        Earlier drafts listed a <code>metrics.json</code> and a <code>report.md</code>. The current
        design keeps the metrics inside <code>result.json</code>, and the written analysis is
        Claude&rsquo;s reply rather than a file. This page will follow whatever the engine actually
        writes.
      </p>
    </>
  );
}
