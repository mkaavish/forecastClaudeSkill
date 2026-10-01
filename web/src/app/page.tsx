import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Terminal } from "@/components/terminal";
import { CodeBlock } from "@/components/code-block";
import { StatusBadge } from "@/components/status-badge";
import { GithubIcon } from "@/components/github-icon";
import { REPO_URL } from "@/lib/site";

const PIPELINE = ["Dataset", "Profile", "Validate", "Backtest", "Select", "Forecast", "Explain"];

const CLAUDE = [
  "Understands what you asked for",
  "Resolves ambiguity: which column, which reading",
  "Orchestrates the analysis",
  "Explains the results in plain English",
];
const PYTHON = [
  "Validates and regularizes the data",
  "Fits models and backtests them",
  "Calculates the error metrics",
  "Selects the model and generates the forecast",
];

export default function Home() {
  return (
    <>
      <section className="mx-auto max-w-6xl px-4 pb-16 pt-16 sm:px-6 sm:pt-24">
        <p className="mb-5">
          <StatusBadge status="early" />
        </p>
        <h1 className="max-w-3xl text-4xl font-semibold tracking-tight sm:text-5xl">
          Time-series forecasting for Claude Code.
        </h1>
        <p className="mt-5 max-w-2xl text-lg leading-8 text-muted">
          <code className="font-mono text-[0.9em] text-foreground">/forecast</code> turns
          time-series datasets into statistically backtested forecasts with automatic model
          selection and plain-English analysis.
        </p>
        <div className="mt-8 flex flex-wrap items-center gap-3">
          <Link
            href="/docs"
            className="inline-flex h-10 items-center gap-2 rounded-md bg-foreground px-4 text-sm font-medium text-background hover:bg-white"
          >
            Get Started <ArrowRight className="size-4" aria-hidden />
          </Link>
          <a
            href={REPO_URL}
            className="inline-flex h-10 items-center gap-2 rounded-md border border-border px-4 text-sm text-foreground hover:bg-surface"
          >
            <GithubIcon className="size-4" /> View on GitHub
          </a>
        </div>
        <div className="mt-12 max-w-2xl">
          <Terminal />
        </div>
      </section>

      <section className="border-t border-border">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
          <h2 className="text-2xl font-semibold tracking-tight">How it works</h2>
          <ol className="mt-6 flex flex-wrap items-center gap-x-2 gap-y-2 font-mono text-sm">
            {PIPELINE.map((step, i) => (
              <li key={step} className="flex items-center gap-2">
                <span className="rounded border border-border bg-surface px-2.5 py-1">{step}</span>
                {i < PIPELINE.length - 1 && (
                  <span aria-hidden className="text-subtle">
                    →
                  </span>
                )}
              </li>
            ))}
          </ol>
          <p className="mt-8 text-lg text-foreground">
            Claude understands the problem. Python does the math.
          </p>
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <div className="rounded-md border border-border p-5">
              <h3 className="font-medium">Claude</h3>
              <ul className="mt-3 space-y-2 text-sm text-muted">
                {CLAUDE.map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            </div>
            <div className="rounded-md border border-border p-5">
              <h3 className="font-medium">Python</h3>
              <ul className="mt-3 space-y-2 text-sm text-muted">
                {PYTHON.map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            </div>
          </div>
          <p className="mt-5 max-w-2xl text-sm text-muted">
            The language model never produces a forecast number. It reads the engine&rsquo;s
            output and explains it.{" "}
            <Link href="/docs/how-it-works" className="text-foreground underline underline-offset-4">
              Read the architecture
            </Link>
            .
          </p>
        </div>
      </section>

      <section className="border-t border-border">
        <div className="mx-auto grid max-w-6xl gap-10 px-4 py-16 sm:px-6 md:grid-cols-2">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">Models are tested, not picked</h2>
            <p className="mt-4 text-muted">
              <code className="font-mono text-[0.9em] text-foreground">/forecast</code> doesn&rsquo;t
              ask Claude which model looks best. Every candidate is scored on held-out history with
              rolling-origin backtesting, and the winner is chosen by a fixed rule.
            </p>
            <p className="mt-4 text-foreground">If a simple baseline performs best, the baseline wins.</p>
            <p className="mt-4 text-sm">
              <Link href="/docs/models" className="text-foreground underline underline-offset-4">
                Models &amp; backtesting
              </Link>
            </p>
          </div>
          <dl className="space-y-5 text-sm">
            <div>
              <dt className="font-mono text-xs uppercase tracking-wide text-subtle">V1 models</dt>
              <dd className="mt-1.5 font-mono text-foreground">
                Naive · Seasonal Naive · AutoETS · AutoARIMA
              </dd>
            </div>
            <div>
              <dt className="font-mono text-xs uppercase tracking-wide text-subtle">Reported metrics</dt>
              <dd className="mt-1.5 font-mono text-foreground">MAE · RMSE · sMAPE</dd>
            </div>
            <div>
              <dt className="font-mono text-xs uppercase tracking-wide text-subtle">Selection</dt>
              <dd className="mt-1.5 text-muted">
                Deterministic. The same data and settings give the same winner.
              </dd>
            </div>
          </dl>
        </div>
      </section>

      <section className="border-t border-border">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
          <h2 className="text-2xl font-semibold tracking-tight">One command</h2>
          <p className="mt-4 max-w-2xl text-muted">
            Point it at a CSV. It finds the date and target columns, checks the series, backtests the
            models, and writes the forecast, a chart, and the metrics to disk.
          </p>
          <div className="mt-6 max-w-2xl">
            <CodeBlock>{`/forecast revenue.csv`}</CodeBlock>
          </div>
          <p className="mt-6 text-sm text-muted">
            <Link href="/docs" className="text-foreground underline underline-offset-4">
              Getting started
            </Link>{" "}
            · <Link href="/docs/usage" className="text-foreground underline underline-offset-4">Usage</Link>{" "}
            ·{" "}
            <Link href="/docs/outputs" className="text-foreground underline underline-offset-4">
              Outputs
            </Link>
          </p>
        </div>
      </section>
    </>
  );
}
