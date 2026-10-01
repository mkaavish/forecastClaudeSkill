import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Terminal } from "@/components/terminal";
import { CodeBlock } from "@/components/code-block";
import { BacktestDiagram } from "@/components/backtest-diagram";
import { GithubIcon } from "@/components/github-icon";
import { REPO_URL } from "@/lib/site";

type Owner = "you" | "python" | "claude";

const PIPELINE: { step: string; owner: Owner }[] = [
  { step: "Dataset", owner: "you" },
  { step: "Profile", owner: "python" },
  { step: "Validate", owner: "python" },
  { step: "Backtest", owner: "python" },
  { step: "Select", owner: "python" },
  { step: "Forecast", owner: "python" },
  { step: "Explain", owner: "claude" },
];

const OWNER_STYLE: Record<Owner, string> = {
  you: "text-subtle",
  python: "text-accent",
  claude: "text-claude",
};

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

function Section({
  index,
  label,
  children,
}: {
  index: string;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border-t border-border">
      <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-24">
        <p className="eyebrow mb-8">
          <span className="text-accent">{index}</span> / {label}
        </p>
        {children}
      </div>
    </section>
  );
}

const linkCls = "text-foreground underline decoration-subtle underline-offset-4 hover:decoration-accent";

export default function Home() {
  return (
    <>
      <section className="mx-auto grid max-w-6xl items-center gap-12 px-4 pb-20 pt-14 sm:px-6 sm:pt-20 lg:grid-cols-[1fr_1.05fr] lg:gap-16">
        <div>
          <p className="eyebrow mb-6 flex items-center gap-2">
            <span aria-hidden className="size-1.5 rounded-full bg-warn" />
            Early development · open source · MIT
          </p>
          <h1 className="text-[2.5rem] font-semibold leading-[1.08] tracking-[-0.035em] sm:text-[3.25rem]">
            Time-series forecasting for Claude Code.
          </h1>
          <p className="mt-6 max-w-lg text-[1.0625rem] leading-8 text-muted">
            <code className="font-mono text-[0.9em] text-foreground">/forecast</code> turns
            time-series datasets into statistically backtested forecasts with automatic model
            selection and plain-English analysis.
          </p>
          <div className="mt-9 flex flex-wrap items-center gap-3">
            <Link
              href="/docs"
              className="inline-flex h-10 items-center gap-2 rounded-md bg-foreground px-4 text-sm font-medium text-background transition-colors hover:bg-white"
            >
              Get Started <ArrowRight className="size-4" aria-hidden />
            </Link>
            <a
              href={REPO_URL}
              className="inline-flex h-10 items-center gap-2 rounded-md border border-border px-4 text-sm text-foreground transition-colors hover:border-subtle"
            >
              <GithubIcon className="size-4" /> View on GitHub
            </a>
          </div>
        </div>
        <Terminal />
      </section>

      <Section index="01" label="How it works">
        <div className="grid gap-10 lg:grid-cols-[1fr_1.4fr] lg:gap-16">
          <div>
            <h2 className="text-3xl font-semibold leading-tight tracking-[-0.025em]">
              Claude understands the problem.
              <br />
              <span className="text-muted">Python does the math.</span>
            </h2>
            <p className="mt-5 max-w-md leading-7 text-muted">
              The language model never produces a forecast number. It decides what to run and
              explains what came back. Every figure is computed by deterministic code.
            </p>
            <p className="mt-5 text-sm">
              <Link href="/docs/how-it-works" className={linkCls}>
                Read the architecture
              </Link>
            </p>
          </div>
          <div className="grid gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-2">
            <div className="bg-background p-6">
              <h3 className="font-mono text-sm text-claude">Claude</h3>
              <ul className="mt-4 space-y-3 text-sm leading-6 text-muted">
                {CLAUDE.map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            </div>
            <div className="bg-background p-6">
              <h3 className="font-mono text-sm text-accent">Python</h3>
              <ul className="mt-4 space-y-3 text-sm leading-6 text-muted">
                {PYTHON.map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        <ol
          aria-label="Pipeline"
          className="mt-16 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-4 lg:grid-cols-7"
        >
          {PIPELINE.map(({ step, owner }, i) => (
            <li key={step} className="bg-background px-4 py-4">
              <span className="num font-mono text-xs text-subtle">{String(i + 1).padStart(2, "0")}</span>
              <p className="mt-2 text-[15px] font-medium">{step}</p>
              <p className={`mt-1 font-mono text-xs ${OWNER_STYLE[owner]}`}>
                {owner === "you" ? "your CSV" : owner === "python" ? "Python" : "Claude"}
              </p>
            </li>
          ))}
        </ol>
      </Section>

      <Section index="02" label="Model selection">
        <div className="grid items-center gap-12 lg:grid-cols-[1fr_1.1fr] lg:gap-16">
          <div>
            <h2 className="text-3xl font-semibold leading-tight tracking-[-0.025em]">
              Models are tested, not picked.
            </h2>
            <p className="mt-5 max-w-md leading-7 text-muted">
              <code className="font-mono text-[0.9em] text-foreground">/forecast</code> doesn&rsquo;t
              ask Claude which model looks best. Each candidate is scored on held-out history with
              rolling-origin backtesting, and a fixed rule chooses the winner.
            </p>
            <p className="mt-5 text-foreground">If a simple baseline performs best, the baseline wins.</p>
            <dl className="mt-8 divide-y divide-border border-y border-border text-sm">
              <div className="flex justify-between gap-6 py-3">
                <dt className="text-subtle">V1 models</dt>
                <dd className="text-right font-mono text-foreground">
                  Naive · Seasonal Naive · AutoETS · AutoARIMA
                </dd>
              </div>
              <div className="flex justify-between gap-6 py-3">
                <dt className="text-subtle">Metrics</dt>
                <dd className="font-mono text-foreground">MAE · RMSE · sMAPE</dd>
              </div>
              <div className="flex justify-between gap-6 py-3">
                <dt className="text-subtle">Selection</dt>
                <dd className="text-right text-foreground">Deterministic</dd>
              </div>
            </dl>
            <p className="mt-6 text-sm">
              <Link href="/docs/models" className={linkCls}>
                Models &amp; backtesting
              </Link>
            </p>
          </div>
          <div className="rounded-lg border border-border bg-surface p-6">
            <BacktestDiagram />
          </div>
        </div>
      </Section>

      <Section index="03" label="Usage">
        <div className="grid gap-10 lg:grid-cols-[1fr_1.1fr] lg:gap-16">
          <div>
            <h2 className="text-3xl font-semibold leading-tight tracking-[-0.025em]">One command.</h2>
            <p className="mt-5 max-w-md leading-7 text-muted">
              Point it at a CSV. It finds the date and target columns, checks the series, backtests
              the models, and writes the forecast, a chart, and the metrics to disk.
            </p>
            <p className="mt-6 flex flex-wrap gap-x-5 gap-y-2 text-sm">
              <Link href="/docs" className={linkCls}>
                Getting started
              </Link>
              <Link href="/docs/usage" className={linkCls}>
                Usage
              </Link>
              <Link href="/docs/outputs" className={linkCls}>
                Outputs
              </Link>
            </p>
          </div>
          <div className="space-y-4">
            <CodeBlock label="claude code">{`/forecast revenue.csv`}</CodeBlock>
            <p className="text-sm text-subtle">
              Not released yet.{" "}
              <Link href="/docs" className={linkCls}>
                See project status
              </Link>
              .
            </p>
          </div>
        </div>
      </Section>
    </>
  );
}
