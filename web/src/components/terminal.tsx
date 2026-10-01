// A static, hand-written mock of a Claude Code session. Nothing here is real output.
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
      <span className="w-32 shrink-0">{k}</span>
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
        <span>example · not a real run</span>
      </figcaption>
      <div
        tabIndex={0}
        role="region"
        aria-label="Example Claude Code session"
        className="overflow-x-auto px-4 py-5 font-mono text-[13px] leading-6 text-muted sm:px-5"
      >
        <div className="min-w-[19rem]">
          <p className="rounded bg-white/[0.04] px-3 py-1.5 text-foreground">
            <span className="text-subtle">&gt; </span>/forecast sales.csv --horizon 30
          </p>

          <Tool cmd="forecast profile sales.csv">
            <p>
              revenue · daily · <span className="num">1,004</span> rows · weekly cycle
            </p>
          </Tool>

          <Tool cmd="forecast run sales.csv --horizon 30">
            <p className="mb-1">Backtested 4 models, 5 rolling windows</p>
            <Row k="Naive" v="12.3% sMAPE" />
            <Row k="Seasonal Naive" v="8.9% sMAPE" />
            <Row k="AutoARIMA" v="6.7% sMAPE" />
            <Row k="AutoETS" v="6.2% sMAPE" />
            <p className="mt-1">
              Selected <span className="text-accent">AutoETS</span>
            </p>
          </Tool>

          <div className="mt-4 flex gap-2 font-sans text-sm leading-6 text-foreground">
            <span aria-hidden className="font-mono text-accent">
              ●
            </span>
            <div className="space-y-3">
              <p>
                AutoETS had the lowest backtest error and beat the best baseline, Seasonal Naive,
                so the engine selected it.
              </p>
              <p>
                Revenue for the next 30 days is forecast at{" "}
                <span className="num font-mono text-[13px]">$782,000</span>. By day 30 the 95%
                interval runs from <span className="num font-mono text-[13px]">$24.1k</span> to{" "}
                <span className="num font-mono text-[13px]">$28.9k</span> a day, so the later days
                are less certain than the first.
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
