// A static, hand-written example. Nothing here is real output.
function Row({ k, v, strong }: { k: string; v: string; strong?: boolean }) {
  return (
    <div className="flex gap-4">
      <span className="w-40 shrink-0 text-subtle">{k}</span>
      <span className={strong ? "text-accent" : "text-foreground"}>{v}</span>
    </div>
  );
}

export function Terminal() {
  return (
    <figure className="overflow-hidden rounded-md border border-border bg-surface">
      <figcaption className="flex items-center justify-between border-b border-border px-4 py-2 font-mono text-xs text-subtle">
        <span>claude code</span>
        <span className="text-warn">example output, not a real run</span>
      </figcaption>
      <div
        tabIndex={0}
        role="region"
        aria-label="Example forecast output"
        className="overflow-x-auto px-4 py-4 font-mono text-[13px] leading-6 text-muted"
      >
        <div className="min-w-max">
          <p>
            <span className="text-subtle">$ </span>
            <span className="text-foreground">/forecast sales.csv --horizon 30</span>
          </p>
          <p className="mt-4 mb-4">Inspecting sales.csv...</p>
          <Row k="Target" v="revenue" />
          <Row k="Frequency" v="daily" />
          <Row k="Observations" v="1,004" />
          <Row k="Seasonality" v="weekly" />
          <p className="mt-4">Backtesting models (5 rolling windows)...</p>
          <div className="mt-4">
            <Row k="Seasonal Naive" v="8.9% sMAPE" />
            <Row k="AutoARIMA" v="6.7% sMAPE" />
            <Row k="AutoETS" v="6.2% sMAPE" />
          </div>
          <div className="mt-4">
            <Row k="Selected" v="AutoETS" strong />
          </div>
          <div className="mt-4">
            <Row k="30-day forecast" v="$782,000 total" />
            <Row k="Day-30 95% interval" v="$24.1k – $28.9k" />
          </div>
        </div>
      </div>
    </figure>
  );
}
