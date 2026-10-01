import type { Metadata } from "next";
import Link from "next/link";
import { Callout } from "@/components/callout";
import { CodeBlock } from "@/components/code-block";
import { StatusBadge } from "@/components/status-badge";

export const metadata: Metadata = { title: "Getting started — /forecast" };

const ROADMAP = [
  "Claude Code /forecast skill",
  "CSV ingestion",
  "Automatic date detection",
  "Automatic target detection",
  "Frequency inference",
  "Data validation",
  "Naive, Seasonal Naive, AutoETS, AutoARIMA",
  "Rolling-origin backtesting",
  "MAE / RMSE / sMAPE",
  "Deterministic model selection",
  "Prediction intervals",
  "Forecast visualization",
  "forecast.csv and result.json",
  "Plain-English analysis",
  "Standalone Python CLI",
  "Automated tests",
  "Synthetic example datasets",
];

export default function GettingStarted() {
  return (
    <>
      <p>
        <StatusBadge status="early" />
      </p>
      <h1>Getting started</h1>
      <p>
        <code>/forecast</code> is an open-source Claude Code skill for statistically backtested
        time-series forecasting. You give it a CSV. A Python engine profiles the data, backtests
        several statistical models, picks one with a fixed rule, and produces a forecast with
        prediction intervals. Claude then explains the result in plain English.
      </p>
      <Callout title="Early development">
        <p>
          The plugin scaffold and CSV loading are under way. The forecasting engine and the skill
          workflow are not built yet, so there is nothing to run today. These docs describe the
          intended V1 behavior; pages mark what is planned.
        </p>
      </Callout>

      <h2>Requirements</h2>
      <ul>
        <li>
          <a href="https://claude.com/claude-code">Claude Code</a>
        </li>
        <li>
          <a href="https://docs.astral.sh/uv/">uv</a>, which fetches Python 3.10 or newer and the
          dependencies on first run
        </li>
        <li>A CSV with a date column and at least one numeric column</li>
      </ul>
      <p>
        The Python stack (statsforecast and friends) takes a few hundred MB, and the first run is
        slower while it installs.
      </p>

      <h2>
        Installation <StatusBadge status="soon" />
      </h2>
      <p>
        There is no released version yet. The plan is to distribute <code>/forecast</code> as a
        Claude Code plugin from the GitHub repository, plus a standalone Python CLI. Install
        commands will be published here once an installable release exists and has been tested.
      </p>

      <h2>
        First forecast <StatusBadge status="planned" />
      </h2>
      <p>Once installed, a forecast is one command inside Claude Code:</p>
      <CodeBlock>{`/forecast sales.csv`}</CodeBlock>
      <p>
        During early development the plugin skill is namespaced by Claude Code, so it is invoked as{" "}
        <code>/forecast:forecast</code>. Whether bare <code>/forecast</code> works depends on the
        Claude Code version; see <Link href="/docs/usage">Usage</Link>.
      </p>

      <h2>Basic workflow</h2>
      <ol>
        <li>
          <strong>Profile.</strong> The engine inspects the CSV and reports the date and target
          candidates, frequency, gaps, and seasonality.
        </li>
        <li>
          <strong>Clarify.</strong> If more than one reading is reasonable (several numeric columns,
          say), Claude asks you instead of guessing.
        </li>
        <li>
          <strong>Run.</strong> The engine backtests the models, selects one, and forecasts.
        </li>
        <li>
          <strong>Explain.</strong> Claude summarizes the results, separating what was observed from
          what is forecast.
        </li>
      </ol>
      <p>
        More detail in <Link href="/docs/how-it-works">How it works</Link>.
      </p>

      <h2>V1 roadmap</h2>
      <p>
        All of the following is <StatusBadge status="planned" />. None of it should be assumed to be
        finished.
      </p>
      <ul>
        {ROADMAP.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <p>
        Not in V1: multiple series per run, holidays, external regressors, Excel or Parquet input,
        intermittent-demand models, and machine-learning models.
      </p>
    </>
  );
}
