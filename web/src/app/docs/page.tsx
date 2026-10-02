import type { Metadata } from "next";
import Link from "next/link";
import { CodeBlock } from "@/components/code-block";

export const metadata: Metadata = { title: "Getting started — /forecast" };

const V1 = [
  "Claude Code /forecast skill and plugin",
  "CSV ingestion",
  "Automatic date detection",
  "Automatic target detection",
  "Frequency inference",
  "Data validation, with 12 refusal codes",
  "Six models: Naive, SeasonalNaive, HistoricAverage, AutoETS, AutoTheta, AutoARIMA",
  "Rolling-origin backtesting",
  "MASE as the ranking metric, with MAE, RMSE and sMAPE reported alongside",
  "Deterministic model selection",
  "80% and 95% prediction intervals, calibrated against the backtest",
  "Forecast chart",
  "forecast.csv and result.json",
  "Plain-English analysis from Claude",
  "Standalone Python CLI",
  "592 automated tests, run on Python 3.10 and 3.12 in CI",
  "Synthetic example datasets",
];

export default function GettingStarted() {
  return (
    <>
      <h1>Getting started</h1>
      <p>
        <code>/forecast</code> is an open-source Claude Code skill for statistically backtested
        time-series forecasting. You give it a CSV. A Python engine profiles the data, backtests
        several statistical models, picks one with a fixed rule, and produces a forecast with
        prediction intervals. Claude then explains the result in plain English.
      </p>
      <p>
        Version 0.1.0 is the first release. Everything is open source under the MIT license.
      </p>

      <h2>Requirements</h2>
      <ul>
        <li>
          <a href="https://claude.com/claude-code">Claude Code</a>
        </li>
        <li>
          <a href="https://docs.astral.sh/uv/">uv</a>, installed with <code>brew install uv</code>{" "}
          or <code>pip install uv</code>. It fetches Python 3.10 or newer and the dependencies for
          you.
        </li>
        <li>A CSV with a date column and at least one numeric column</li>
      </ul>
      <p>
        The first run takes about a minute while dependencies install. The Python stack
        (statsforecast and friends) is a few hundred MB.
      </p>

      <h2>Installation</h2>
      <p>Inside Claude Code:</p>
      <CodeBlock>{`/plugin marketplace add mkaavish/forecastClaudeSkill
/plugin install forecast@forecast-skill`}</CodeBlock>

      <h2>First forecast</h2>
      <CodeBlock>{`/forecast:forecast sales.csv`}</CodeBlock>
      <p>
        The command is <code>/forecast:forecast</code>. Claude Code namespaces plugin skills, so a
        bare <code>/forecast</code> does not work (tested on Claude Code 2.1.119).
      </p>

      <h2>Basic workflow</h2>
      <ol>
        <li>
          <strong>Run.</strong> Claude calls the engine once. The engine profiles the CSV, checks
          it, backtests the models, selects one, and forecasts.
        </li>
        <li>
          <strong>Clarify, if needed.</strong> If more than one reading is reasonable (several
          numeric columns, say), the engine stops and returns questions. Claude asks you, then
          re-runs with your answers.
        </li>
        <li>
          <strong>Explain.</strong> Claude summarizes the results, separating what was observed from
          what is forecast.
        </li>
      </ol>
      <p>
        More detail in <Link href="/docs/how-it-works">How it works</Link>.
      </p>

      <h2>What&rsquo;s in V1</h2>
      <ul>
        {V1.map((item) => (
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
