// Real output of `forecast run examples/retail_sales.csv --horizon 30`, shown as a Claude Code session.
function Tool({ cmd, children }: { cmd: string; children: React.ReactNode }) {
  return (
    <div className="mt-4">
      <p className="text-foreground">
        <span className="text-subtle">● </span>
        Bash<span className="text-muted">({cmd})</span>
      </p>
      <div className="mt-0.5 flex gap-2 text-muted">
        <span aria-hidden className="text-subtle">
          ⎿
        </span>
        <div className="min-w-0">{children}</div>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-4">
      <span className="w-36 shrink-0">{k}</span>
      <span className="num text-foreground">{v}</span>
    </div>
  );
}

export function Terminal() {
  return (
    <figure className="overflow-hidden rounded-lg border border-border bg-surface shadow-[0_24px_60px_-30px_rgba(0,0,0,0.9)]">
      <figcaption className="flex items-center justify-between border-b border-border px-4 py-2.5 font-mono text-xs text-subtle">
        <span>
          <span className="text-accent">✻</span> Claude Code
        </span>
        <span>examples/retail_sales.csv</span>
      </figcaption>
      <div
        tabIndex={0}
        role="region"
        aria-label="Claude Code session forecasting retail_sales.csv"
        className="overflow-x-auto px-4 py-5 font-mono text-[13px] leading-6 text-muted sm:px-5"
      >
        <div className="min-w-[19rem]">
          <p className="rounded bg-white/[0.04] px-3 py-1.5 text-foreground">
            <span className="text-subtle">&gt; </span>/forecast:forecast retail_sales.csv --horizon 30
          </p>

          <Tool cmd="forecast run retail_sales.csv --horizon 30">
            <p>
              sales · daily · <span className="num">731</span> observations
            </p>
            <p className="mb-1">5 rolling windows of 30 steps · MASE</p>
            <Row k="Naive" v="3.17" />
            <Row k="SeasonalNaive" v="1.21" />
            <Row k="HistoricAverage" v="4.96" />
            <Row k="AutoETS" v="0.974" />
            <Row k="AutoTheta" v="0.974" />
            <Row k="AutoARIMA" v="0.977" />
            <p className="mt-1">
              Selected <span className="text-accent">AutoETS</span> · beat SeasonalNaive by 19%
            </p>
          </Tool>

          <div className="mt-4 flex gap-2 font-sans text-sm leading-6 text-foreground">
            <span aria-hidden className="font-mono text-accent">
              ●
            </span>
            <div className="space-y-3">
              <p>
                AutoETS tied AutoTheta on MASE (0.974), and ties go to the simpler model. It beat
                the best baseline, SeasonalNaive, by 19%, well past the 5% required.
              </p>
              <p>
                The next 30 days sum to{" "}
                <span className="num font-mono text-[13px]">469,257</span>, up 3.0% on the previous
                30 (<span className="num font-mono text-[13px]">455,373</span>). On the last day the
                95% interval runs from{" "}
                <span className="num font-mono text-[13px]">14,910</span> to{" "}
                <span className="num font-mono text-[13px]">18,380</span>.
              </p>
            </div>
          </div>

          <p className="mt-5 rounded border border-border px-3 py-1.5 text-subtle">
            <span aria-hidden>&gt; </span>
            <span aria-hidden className="inline-block h-[1em] w-[0.55em] translate-y-[2px] bg-subtle/60" />
          </p>
        </div>
      </div>
    </figure>
  );
}
