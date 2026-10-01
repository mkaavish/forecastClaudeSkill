// A static, hand-written example. Nothing here is real output.
function Row({ k, v, tone }: { k: string; v: string; tone?: "accent" }) {
  return (
    <div className="flex gap-4">
      <span className="w-44 shrink-0 text-subtle">{k}</span>
      <span className={`num ${tone === "accent" ? "text-accent" : "text-foreground"}`}>{v}</span>
    </div>
  );
}

function Rule() {
  return <div className="my-4 border-t border-dashed border-border" aria-hidden />;
}

export function Terminal() {
  return (
    <figure className="overflow-hidden rounded-lg border border-border bg-surface shadow-[0_24px_60px_-30px_rgba(0,0,0,0.9)]">
      <figcaption className="flex items-center justify-between border-b border-border px-4 py-2.5 font-mono text-xs text-subtle">
        <span className="hidden sm:inline">~/analysis</span>
        <span>example output · not a real run</span>
      </figcaption>
      <div
        tabIndex={0}
        role="region"
        aria-label="Example forecast output"
        className="overflow-x-auto px-5 py-5 font-mono text-[13px] leading-6 text-muted"
      >
        <div className="min-w-max">
          <p>
            <span className="text-accent">$ </span>
            <span className="text-foreground">/forecast sales.csv --horizon 30</span>
          </p>
          <Rule />
          <p className="mb-2">Inspecting sales.csv</p>
          <Row k="Target" v="revenue" />
          <Row k="Frequency" v="daily" />
          <Row k="Observations" v="1,004" />
          <Row k="Seasonality" v="weekly" />
          <Rule />
          <p className="mb-2">Backtesting models · 5 rolling windows</p>
          <Row k="Seasonal Naive" v="8.9% sMAPE" />
          <Row k="AutoARIMA" v="6.7% sMAPE" />
          <Row k="AutoETS" v="6.2% sMAPE" />
          <Rule />
          <Row k="Selected" v="AutoETS" tone="accent" />
          <Row k="30-day forecast" v="$782,000 total" />
          <Row k="Day-30 95% interval" v="$24.1k – $28.9k" />
        </div>
      </div>
    </figure>
  );
}
