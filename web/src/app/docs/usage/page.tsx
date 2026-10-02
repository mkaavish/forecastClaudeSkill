import type { Metadata } from "next";
import { CodeBlock } from "@/components/code-block";

export const metadata: Metadata = { title: "Usage — /forecast" };

export default function Usage() {
  return (
    <>
      <h1>Usage</h1>
      <p>
        Inside Claude Code the command is <code>/forecast:forecast</code>. The same engine also
        runs as a standalone CLI, covered at the end of this page.
      </p>

      <h2>Forecast a file</h2>
      <CodeBlock>{`/forecast:forecast sales.csv`}</CodeBlock>
      <p>
        Detects the date and target columns, infers the frequency, and uses a default horizon for
        that frequency.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Frequency</th>
              <th>Default horizon</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>Hourly</td><td>24</td></tr>
            <tr><td>Daily</td><td>28</td></tr>
            <tr><td>Business daily</td><td>20</td></tr>
            <tr><td>Weekly</td><td>13</td></tr>
            <tr><td>Monthly</td><td>12</td></tr>
            <tr><td>Quarterly</td><td>4</td></tr>
            <tr><td>Yearly</td><td>3</td></tr>
          </tbody>
        </table>
      </div>

      <h2>Set the horizon</h2>
      <CodeBlock>{`/forecast:forecast sales.csv --horizon 30`}</CodeBlock>
      <p>
        <code>--horizon</code> is the number of future periods to forecast, in the data&rsquo;s own
        frequency. The backtest uses the same horizon. If the history is too short to backtest at
        that length, the test horizon is shortened with a warning. Below a floor the run refuses and
        tells you the longest horizon the history can support.
      </p>

      <h2>Choose the target</h2>
      <CodeBlock>{`/forecast:forecast revenue.csv --target revenue`}</CodeBlock>
      <p>
        Use <code>--target</code> when the file has several numeric columns. Without it, Claude
        asks which one you mean.
      </p>

      <h2>Flags</h2>
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
              <td><code>--horizon N</code></td>
              <td>Number of future periods to forecast</td>
            </tr>
            <tr>
              <td><code>--target COL</code></td>
              <td>Name the column to forecast</td>
            </tr>
            <tr>
              <td><code>--date COL</code></td>
              <td>Name the date column instead of detecting it</td>
            </tr>
            <tr>
              <td><code>--date-order dmy|mdy</code></td>
              <td>Resolve day-first or month-first dates such as <code>01/02/2026</code></td>
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
              <td>Forecast one slice of a multi-column file. Repeatable.</td>
            </tr>
            <tr>
              <td><code>--agg sum|mean</code></td>
              <td>How to combine rows that share a timestamp</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p>
        One series is forecast per run. Grouped forecasting (one forecast per store, product, and
        so on) is not in V1.
      </p>

      <h2>Invocation name</h2>
      <p>
        The command is <code>/forecast:forecast</code>. Claude Code namespaces plugin skills, and a
        bare <code>/forecast</code> does not work (tested on Claude Code 2.1.119).
      </p>

      <h2>Standalone CLI</h2>
      <p>
        The engine runs without Claude. <code>forecast FILE</code> is the same as{" "}
        <code>forecast run FILE</code>, and <code>forecast profile FILE</code> prints the dataset
        profile as JSON.
      </p>
      <CodeBlock>{`forecast sales.csv --horizon 30
forecast profile sales.csv`}</CodeBlock>
      <p>
        Without Claude you get the engine&rsquo;s templated text report instead of a written
        explanation. Add <code>--json</code> to get the machine-readable result on stdout.
      </p>
      <p>
        Run it from a clone of the repository with the <code>bin/forecast</code> wrapper, which
        uses <code>uv</code>, or install it as a tool with <code>uv tool install .</code>.
      </p>

      <h3>Exit codes</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Code</th>
              <th>Meaning</th>
            </tr>
          </thead>
          <tbody>
            <tr><td><code>0</code></td><td>ok</td></tr>
            <tr><td><code>2</code></td><td>usage error</td></tr>
            <tr><td><code>3</code></td><td>needs input: the data is ambiguous and the engine returns questions</td></tr>
            <tr><td><code>4</code></td><td>refused: the data can&rsquo;t support a trustworthy forecast</td></tr>
          </tbody>
        </table>
      </div>
    </>
  );
}
