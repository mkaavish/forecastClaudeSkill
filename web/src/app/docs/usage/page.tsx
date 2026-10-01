import type { Metadata } from "next";
import { Callout } from "@/components/callout";
import { CodeBlock } from "@/components/code-block";
import { StatusBadge } from "@/components/status-badge";

export const metadata: Metadata = { title: "Usage — /forecast" };

export default function Usage() {
  return (
    <>
      <h1>Usage</h1>
      <Callout title="Nothing here runs yet">
        <p>
          This page documents the intended syntax. Every command and flag below is{" "}
          <StatusBadge status="planned" /> until the engine ships.
        </p>
      </Callout>

      <h2>Forecast a file</h2>
      <CodeBlock>{`/forecast sales.csv`}</CodeBlock>
      <p>
        Detects the date and target columns, infers the frequency, and uses a default horizon for
        that frequency: 28 periods for daily data, 13 for weekly, 12 for monthly, 4 for quarterly.
      </p>

      <h2>Set the horizon</h2>
      <CodeBlock>{`/forecast sales.csv --horizon 30`}</CodeBlock>
      <p>
        <code>--horizon</code> is the number of future periods to forecast, in the data&rsquo;s own
        frequency. The backtest uses the same horizon. If the history is too short to backtest it
        reliably, the run is refused or warns rather than pretending.
      </p>

      <h2>Choose the target</h2>
      <CodeBlock>{`/forecast revenue.csv --target revenue`}</CodeBlock>
      <p>
        Use <code>--target</code> when the file has several numeric columns. Without it, Claude
        asks which one you mean.
      </p>

      <h2>Other planned flags</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Flag</th>
              <th>Purpose</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><code>--date COL</code></td>
              <td>Name the date column instead of detecting it</td>
            </tr>
            <tr>
              <td><code>--output DIR</code></td>
              <td>Where to write results (default <code>./forecast-output/&lt;name&gt;/</code>)</td>
            </tr>
            <tr>
              <td><code>--fill interpolate|zero</code></td>
              <td>How to fill missing timestamps</td>
            </tr>
            <tr>
              <td><code>--where col=value</code></td>
              <td>Forecast one slice of a multi-column file</td>
            </tr>
            <tr>
              <td><code>--agg sum|mean</code></td>
              <td>How to combine rows that share a timestamp</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p>
        These may change before V1. Grouped forecasting (one forecast per store, product, and so
        on) is not in V1.
      </p>

      <h2>Invocation name</h2>
      <p>
        Claude Code namespaces plugin skills. In testing on Claude Code 2.1.119, the skill in this
        plugin was invoked as <code>/forecast:forecast</code>, and a root-level skill file was not
        loaded at all. Newer versions may behave differently, so the docs use <code>/forecast</code>{" "}
        as the short name and this page will be updated once the install path is verified.
      </p>

      <h2>Standalone CLI</h2>
      <p>
        <StatusBadge status="planned" /> The engine is also meant to run without Claude:{" "}
        <code>forecast profile FILE</code> to inspect a dataset and <code>forecast run FILE</code>{" "}
        to produce a forecast. In that mode you get a templated text summary instead of Claude&rsquo;s
        explanation.
      </p>

      <h2>Status</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Capability</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Plugin scaffold and launcher</td>
              <td><StatusBadge status="early" label="In progress" /></td>
            </tr>
            <tr>
              <td>CSV loading and column detection</td>
              <td><StatusBadge status="early" label="In progress" /></td>
            </tr>
            <tr>
              <td>Profiling, backtesting, selection, forecasting</td>
              <td><StatusBadge status="planned" /></td>
            </tr>
            <tr>
              <td>Skill workflow and Claude explanation</td>
              <td><StatusBadge status="planned" /></td>
            </tr>
          </tbody>
        </table>
      </div>
    </>
  );
}
