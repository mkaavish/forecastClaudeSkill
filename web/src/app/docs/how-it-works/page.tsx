import type { Metadata } from "next";
import Link from "next/link";
import { CodeBlock } from "@/components/code-block";

export const metadata: Metadata = { title: "How it works — /forecast" };

export default function HowItWorks() {
  return (
    <>
      <h1>How it works</h1>
      <p>
        Claude understands the problem. Python does the math. The two halves have separate jobs and
        a narrow interface between them: one command and a set of files.
      </p>

      <h2>The pipeline</h2>
      <CodeBlock>{`Claude
  → dataset profiler
  → validation
  → forecasting engine
  → backtesting
  → model selection
  → forecast
  → Claude explanation`}</CodeBlock>

      <h2>What Claude does</h2>
      <ul>
        <li>Parses what you asked for and picks the engine arguments.</li>
        <li>
          Runs one command, <code>forecast run</code>. If the data is ambiguous (several numeric
          columns, an unclear date format, gaps that might mean zero), the engine exits with code 3
          and a list of questions. Claude asks you, then re-runs with the flags you chose.
        </li>
        <li>
          Reads the engine&rsquo;s text report and, when needed, <code>result.json</code>, and
          explains it: what was observed, what is forecast, how reliable the backtest says it is,
          and which warnings matter.
        </li>
      </ul>

      <h2>What Python does</h2>
      <ul>
        <li>
          <strong>Profile and validate.</strong> Frequency, missing timestamps, duplicates,
          outliers, trend, seasonality. It can refuse a dataset that is too short or constant.
        </li>
        <li>
          <strong>Backtest.</strong> Each eligible model is fit and scored on several held-out
          windows.
        </li>
        <li>
          <strong>Select.</strong> A fixed rule picks the winner from the backtest errors.
        </li>
        <li>
          <strong>Forecast.</strong> The winner is refit on all history and produces the forecast
          and prediction intervals.
        </li>
        <li>
          <strong>Write outputs.</strong> CSV, JSON, and a chart. See{" "}
          <Link href="/docs/outputs">Outputs</Link>.
        </li>
      </ul>

      <h2>Why Claude doesn&rsquo;t calculate the forecast</h2>
      <p>
        A language model asked to predict numbers from a CSV produces plausible-looking answers with
        no error estimate and no way to check them. It is also not repeatable: the same file can
        give different numbers on different runs.
      </p>
      <p>
        Statistical models fit by code are testable. They can be backtested against history,
        compared with simple baselines, and re-run to get the same answer. Claude is good at the
        parts code is bad at: working out what you meant and explaining the result in your terms.
      </p>
      <p>
        Claude also never picks the winning model and never does arithmetic on the results. When
        Claude needs a number to say something true, the engine supplies it.
      </p>

      <h2>Privacy and cost</h2>
      <p>
        Claude never reads the raw rows. It works from the engine&rsquo;s report and result file,
        so a large CSV doesn&rsquo;t have to pass through the model.
      </p>
    </>
  );
}
