"""A self-contained HTML dashboard for one forecast run (``dashboard.html``).

The engine writes it, so every figure on the page is a value the engine computed; the page
only draws and arranges them. It has no external dependencies (inline CSS, JS and SVG) so it
opens from disk in any browser, and it follows the Artifact page contract (theme tokens with
light, dark and explicit-toggle states, a 16px gutter, phone-width layout) so the same file
can be published as a Claude Artifact unchanged.

The file starts with a doctype so it renders in standards mode on its own; inside an Artifact
wrapper that stray doctype is ignored by the HTML parser.
"""

from __future__ import annotations

import html
import json
import re

import pandas as pd

from forecast.outputs import _num, _pattern
from forecast.schema import RunResult

HISTORY_CAP = 1500  # most recent observations embedded; the chart says when it is showing a subset

_PLACEHOLDER = re.compile(r"__([A-Z_]+)__")
_REASONS = {
    "beat_baseline_by_margin": "Beat the best baseline by more than the required margin",
    "baseline_within_margin": "A complex model was better, but by less than the required margin",
    "baseline_best": "No complex model beat the baseline",
    "only_baselines_ran": "Only baseline models ran",
    "no_baseline_ran": "Every baseline failed; best remaining model used",
}


def render_dashboard(result: RunResult, history: pd.DataFrame, forecast: pd.DataFrame) -> str:
    """Return the dashboard as one HTML document."""
    f, sel, inp = result.forecast, result.selection, result.input
    e = html.escape
    target = inp.target_column

    data = _page_data(result, history, forecast)
    # indent=0 puts one value per line, so the embedded data is reviewable and no line is huge
    payload = json.dumps(data, indent=0, separators=(",", ":")).replace("<", "\\u003c")

    n_warn = sum(w.severity == "warn" for w in result.warnings)
    status = "No warnings" if n_warn == 0 else f"{n_warn} warning{'s' if n_warn != 1 else ''}"
    change = ""
    if f.change_vs_prior is not None:
        arrow = "▲" if f.change_vs_prior > 0 else "▼" if f.change_vs_prior < 0 else "■"
        change = (
            f'<p class="hero-delta"><span aria-hidden="true">{arrow}</span> {f.change_vs_prior:+.1%} '
            f"vs the previous {f.horizon} periods ({_num(f.previous_total)})</p>"
        )
    chosen = next(m for m in result.backtest.models if m.name == f.model)
    mase = chosen.metrics.mase if chosen.metrics else None
    score = f"MASE {mase:.2f}" if mase is not None else "backtest MAE"
    plan = result.backtest.plan
    iv = result.intervals

    facts = [
        ("Observations", f"{inp.n_obs} {inp.frequency_name} ({inp.start[:10]} to {inp.end[:10]})"),
        ("Pattern", _pattern(result)),
    ]
    out = result.profile.outliers
    facts.append(
        (
            "Outliers",
            f"{out.n_outliers} flagged, kept in the data" if out.n_outliers else "none flagged",
        )
    )
    if inp.n_imputed:
        facts.append(
            (
                "Filled periods",
                f"{inp.n_imputed} (longest gap {inp.longest_gap}), by {inp.fill_policy}",
            )
        )
    if result.profile.intermittency.zero_heavy:
        facts.append(("Zero values", f"{result.profile.stats.zero_fraction:.0%} of observations"))
    fact_rows = "".join(f"<div><dt>{e(k)}</dt><dd>{e(v)}</dd></div>" for k, v in facts)

    title = f"{target[:1].upper()}{target[1:]} Forecast"
    growth = f.interval_width_growth
    values = {
        "TITLE": e(title),
        "TARGET": e(target),
        "SUBTITLE": e(f"{f.horizon} {inp.frequency_name} periods, {f.start[:10]} to {f.end[:10]}"),
        "STATUS": e(status),
        "STATUS_CLASS": "warn" if n_warn else "ok",
        "HERO_VALUE": e(_num(f.total)),
        "HERO_DELTA": change,
        "MEAN": e(_num(f.mean)),
        "MODEL": e(f.model),
        "MODEL_SUB": e(f"{score}, {plan.n_windows} backtest windows"),
        "LAST_DATE": e(f.last.ds[:10]),
        "LAST_RANGE": e(f"{_num(f.last.lo_80)} to {_num(f.last.hi_80)}"),
        "GROWTH": e(
            "interval width unchanged"
            if growth in (None, 1.0)
            else f"interval {growth:.2f}x as wide as at the start"
        ),
        "REASON": e(_REASONS[sel.reason]),
        "EXPLANATION": e(sel.explanation),
        "MARGIN": e(f"{sel.required_margin:.0%}"),
        "INTERVALS": e(_interval_text(iv)),
        "FACTS": fact_rows,
        "FOOTER": e(_footer(result)),
        "DATA": payload,
    }
    # One pass, so text that happens to look like a placeholder (a column named __DATA__) is never re-substituted.
    return _PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), _TEMPLATE)


def _interval_text(iv) -> str:
    text = (
        f"The model's own 80% interval contained {iv.native_coverage_80:.0%} of backtest actuals."
    )
    if iv.method == "calibrated":
        text += f" It was too narrow, so intervals were widened by {iv.factor_80:.2f}x (80%) and {iv.factor_95:.2f}x (95%)."
    return text


def _footer(result: RunResult) -> str:
    m = result.meta
    return (
        f"Computed by forecast {m.forecast_version} with StatsForecast {m.statsforecast_version} "
        f"in {m.elapsed_seconds}s. This page only displays the engine's results."
    )


def _page_data(result: RunResult, history: pd.DataFrame, forecast: pd.DataFrame) -> dict:
    shown = history.tail(HISTORY_CAP).reset_index(drop=True)
    imputed = [int(i) for i in shown.index[shown["imputed"].to_numpy()]]
    models = []
    for rank, r in enumerate(result.selection.ranking, start=1):
        m = next(x for x in result.backtest.models if x.name == r.name)
        mt = m.metrics
        models.append({
            "name": m.name, "kind": m.kind, "rank": rank, "score": r.score,
            "mase": mt.mase, "mae": mt.mae, "rmse": mt.rmse, "smape": mt.smape,
            "cov80": mt.coverage_80, "windowMae": mt.window_mae, "note": m.reason,
        })  # fmt: skip
    others = [
        {"name": m.name, "kind": m.kind, "status": m.status, "reason": m.reason}
        for m in result.backtest.models
        if m.status != "ok"
    ]
    sel = result.selection
    comparator = sel.best_baseline if sel.winner_kind == "complex" else sel.best_complex
    return {
        "target": result.input.target_column,
        "model": result.forecast.model,
        "selected": sel.winner,
        "comparator": comparator,
        "metric": sel.metric,
        "horizon": result.forecast.horizon,
        "totalHistory": len(history),
        "history": {
            "ds": [pd.Timestamp(t).isoformat() for t in shown["ds"]],
            "y": [round(float(v), 6) for v in shown["y"]],
            "imputed": imputed,
        },
        "forecast": {
            "ds": [pd.Timestamp(t).isoformat() for t in forecast["ds"]],
            **{
                c: [float(v) for v in forecast[c]]
                for c in ("forecast", "lo_80", "hi_80", "lo_95", "hi_95")
            },
        },
        "models": models,
        "excluded": others,
        "windows": result.backtest.plan.n_windows,
        "warnings": [
            {"code": w.code, "severity": w.severity, "message": w.message} for w in result.warnings
        ],
    }


_TEMPLATE = r"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>__TITLE__</title>
<style>
/* Layout: one calm column; the number leads, then the chart, then the evidence behind the model choice. */
:root {
  --bg: #f4f4f1; --surface: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e; --ink-3: #6f6e68;
  --line: #e4e3de; --grid: #ecebe7; --focus: #2a78d6;
  --observed: #2a78d6; --forecast: #eb6834; --baseline: #8a897f; --complex: #2a78d6;
  --warn: #fab219; --ok: #0ca30c; --chip: #efeee9;
  --band80: rgba(235,104,52,.26); --band95: rgba(235,104,52,.12);
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #121211; --surface: #1a1a19; --ink: #f4f4f0; --ink-2: #c3c2b7; --ink-3: #9a9990;
    --line: #2d2d2a; --grid: #292926; --focus: #3987e5;
    --observed: #3987e5; --forecast: #d95926; --baseline: #8d8c84; --complex: #3987e5;
    --warn: #fab219; --ok: #0ca30c; --chip: #262624;
    --band80: rgba(217,89,38,.34); --band95: rgba(217,89,38,.16);
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #121211; --surface: #1a1a19; --ink: #f4f4f0; --ink-2: #c3c2b7; --ink-3: #9a9990;
  --line: #2d2d2a; --grid: #292926; --focus: #3987e5;
  --observed: #3987e5; --forecast: #d95926; --baseline: #8d8c84; --complex: #3987e5;
  --warn: #fab219; --ok: #0ca30c; --chip: #262624;
  --band80: rgba(217,89,38,.34); --band95: rgba(217,89,38,.16);
  color-scheme: dark;
}
* { box-sizing: border-box; }
body {
  background: var(--bg); color: var(--ink); margin: 0;
  font: 14px/1.5 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  padding-inline: 16px; padding-block: 24px 40px;
  -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 1120px; margin-inline: auto; display: grid; gap: 16px; }
h1, h2, p, dl, dd, ul { margin: 0; }
h1 { font-size: 1.375rem; font-weight: 650; letter-spacing: -.01em; text-wrap: balance; }
h2 { font-size: .8125rem; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--ink-2); }
.muted { color: var(--ink-2); }
.small { font-size: .8125rem; }
header { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: flex-start; justify-content: space-between; }
header .sub { color: var(--ink-2); margin-top: 2px; }
.pill { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 999px;
  background: var(--chip); font-size: .8125rem; color: var(--ink); white-space: nowrap; }
.pill i { width: 8px; height: 8px; border-radius: 50%; background: var(--ok); }
.pill.warn i { background: var(--warn); }
.card { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 16px; min-width: 0; }
.card > h2 { margin-bottom: 12px; }
.kpis { display: grid; gap: 16px; grid-template-columns: 1.4fr repeat(3, 1fr); }
.kpi { display: grid; gap: 4px; align-content: start; }
.kpi .label { color: var(--ink-2); font-size: .8125rem; }
.kpi .value { font-size: 1.75rem; font-weight: 650; letter-spacing: -.02em; line-height: 1.15; }
.kpi .note { color: var(--ink-2); font-size: .8125rem; }
.hero .value { font-size: 3.25rem; letter-spacing: -.03em; line-height: 1.05; }
.hero-delta { color: var(--ink-2); font-size: .9375rem; }
.chart-head { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.legend { display: flex; flex-wrap: wrap; gap: 4px 6px; }
.legend button, .seg button {
  font: inherit; color: var(--ink); background: transparent; border: 1px solid var(--line);
  border-radius: 6px; padding: 3px 9px; cursor: pointer; display: inline-flex; align-items: center; gap: 6px;
}
.legend button[aria-pressed="false"] { color: var(--ink-3); text-decoration: line-through; }
.legend .key { width: 14px; height: 0; border-top: 2px solid currentColor; }
.legend .sw { width: 12px; height: 12px; border-radius: 3px; }
.seg { display: inline-flex; }
.seg button { border-radius: 0; margin-left: -1px; }
.seg button:first-child { border-radius: 6px 0 0 6px; margin-left: 0; }
.seg button:last-child { border-radius: 0 6px 6px 0; }
.seg button[aria-pressed="true"] { background: var(--chip); font-weight: 600; }
button:focus-visible, .plot:focus-visible, summary:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.plot { position: relative; outline-offset: 4px; border-radius: 6px; touch-action: pan-y; }
.plot svg { display: block; width: 100%; height: auto; overflow: visible; }
.plot text { fill: var(--ink-2); font: 11px ui-sans-serif, system-ui, sans-serif; }
.tip { position: absolute; pointer-events: none; z-index: 2; background: var(--surface); color: var(--ink);
  border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; font-size: .8125rem; min-width: 150px;
  box-shadow: 0 6px 20px rgba(0,0,0,.16); }
.tip b { display: block; margin-bottom: 4px; }
.tip div { display: flex; justify-content: space-between; gap: 14px; color: var(--ink-2); }
.tip div span:last-child { color: var(--ink); font-variant-numeric: tabular-nums; }
.two { display: grid; gap: 16px; grid-template-columns: 1.15fr 1fr; align-items: start; }
.why p + p { margin-top: 8px; }
.tag { display: inline-block; padding: 1px 8px; border-radius: 999px; background: var(--chip); font-size: .75rem; color: var(--ink-2); }
.bars { display: grid; gap: 10px; margin-top: 12px; }
.bar-row { display: grid; grid-template-columns: minmax(96px, 128px) 1fr; gap: 10px; align-items: center; }
.bar-row .name { font-size: .8125rem; overflow-wrap: anywhere; }
.bar-row .name small { display: block; color: var(--ink-3); font-size: .6875rem; }
.track { display: flex; align-items: center; gap: 8px; min-width: 0; }
.fill { height: 14px; border-radius: 0 4px 4px 0; min-width: 2px; }
.fill.baseline { background: var(--baseline); } .fill.complex { background: var(--complex); }
.sel .fill { box-shadow: 0 0 0 2px var(--surface), 0 0 0 4px var(--forecast); }
.val { font-variant-numeric: tabular-nums; font-size: .8125rem; white-space: nowrap; }
.keyline { display: flex; flex-wrap: wrap; gap: 4px 14px; margin-top: 10px; color: var(--ink-2); font-size: .75rem; }
.keyline span::before { content: ""; display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 6px; vertical-align: -1px; }
.keyline .b::before { background: var(--baseline); } .keyline .c::before { background: var(--complex); }
.keyline .s::before { background: transparent; box-shadow: 0 0 0 2px var(--forecast); }
.wins { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); gap: 10px; align-items: end; height: 150px; margin-top: 12px; }
.win { display: grid; grid-template-rows: 1fr auto; gap: 6px; height: 100%; min-width: 0; }
.pair { display: flex; align-items: flex-end; gap: 4px; justify-content: center; min-height: 0; }
.pair i { display: block; width: min(22px, 40%); border-radius: 4px 4px 0 0; min-height: 2px; }
.win small { text-align: center; color: var(--ink-3); font-size: .6875rem; }
table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; font-size: .8125rem; }
th, td { text-align: right; padding: 6px 10px; border-bottom: 1px solid var(--line); white-space: nowrap; }
th:first-child, td:first-child { text-align: left; }
th { color: var(--ink-2); font-weight: 600; }
tr.sel td { font-weight: 650; }
.scroll { overflow-x: auto; }
dl.facts { display: grid; gap: 10px; }
dl.facts div { display: grid; grid-template-columns: 120px 1fr; gap: 12px; }
dl.facts dt { color: var(--ink-2); }
dl.facts dd { overflow-wrap: anywhere; }
ul.warns { list-style: none; padding: 0; display: grid; gap: 10px; }
ul.warns li { display: grid; grid-template-columns: auto 1fr; gap: 4px 10px; align-items: baseline; }
.sev { display: inline-flex; gap: 6px; align-items: center; font-size: .75rem; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; }
.sev.warn::before { content: "▲"; color: var(--warn); }
.sev.info::before { content: "●"; color: var(--ink-3); }
.code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .75rem; color: var(--ink-2); }
details summary { cursor: pointer; color: var(--ink-2); }
details[open] summary { margin-bottom: 8px; }
footer { color: var(--ink-3); font-size: .75rem; padding-top: 4px; }
@media (max-width: 860px) {
  .kpis { grid-template-columns: 1fr 1fr; } .hero { grid-column: 1 / -1; }
  .two { grid-template-columns: 1fr; }
}
@media (max-width: 480px) {
  .hero .value { font-size: 2.75rem; } .kpis > :last-child { grid-column: 1 / -1; } dl.facts div { grid-template-columns: 1fr; gap: 0; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
</style>
<div class="wrap">
  <header>
    <div>
      <h1>__TARGET__ forecast</h1>
      <p class="sub">__SUBTITLE__</p>
    </div>
    <span class="pill __STATUS_CLASS__"><i aria-hidden="true"></i>__STATUS__</span>
  </header>

  <section class="kpis" aria-label="Headline figures">
    <div class="card kpi hero">
      <span class="label">Sum of forecasts</span>
      <span class="value">__HERO_VALUE__</span>
      __HERO_DELTA__
    </div>
    <div class="card kpi">
      <span class="label">Mean per period</span>
      <span class="value">__MEAN__</span>
    </div>
    <div class="card kpi">
      <span class="label">Selected model</span>
      <span class="value">__MODEL__</span>
      <span class="note">__MODEL_SUB__</span>
    </div>
    <div class="card kpi">
      <span class="label">80% interval at __LAST_DATE__</span>
      <span class="value">__LAST_RANGE__</span>
      <span class="note">__GROWTH__</span>
    </div>
  </section>

  <section class="card" aria-label="Forecast chart">
    <div class="chart-head">
      <div class="legend" id="legend"></div>
      <div class="seg" id="range" role="group" aria-label="History shown">
        <button type="button" data-range="recent" aria-pressed="true">Recent</button>
        <button type="button" data-range="all" aria-pressed="false">All history</button>
      </div>
    </div>
    <div class="plot" id="plot" tabindex="0"></div>
    <p class="small muted" id="plot-note" style="margin-top:8px"></p>
    <details style="margin-top:12px">
      <summary>Show the forecast as a table</summary>
      <div class="scroll"><table id="fc-table"></table></div>
    </details>
  </section>

  <section class="two">
    <div class="card why">
      <h2>Why this model</h2>
      <p><span class="tag">__REASON__</span></p>
      <p>__EXPLANATION__</p>
      <p class="muted small">A complex model must beat the best baseline by __MARGIN__. __INTERVALS__</p>
      <div class="bars" id="bars" aria-label="Backtest error by model"></div>
      <div class="keyline"><span class="b">Baseline</span><span class="c">Complex</span><span class="s">Selected</span><span>Lower is better</span></div>
    </div>
    <div class="card">
      <h2>Error by backtest window</h2>
      <p class="muted small" id="wins-title"></p>
      <div class="wins" id="wins"></div>
      <div class="keyline" id="wins-key"></div>
    </div>
  </section>

  <section class="card">
    <h2>Backtest scores</h2>
    <div class="scroll"><table id="scores"></table></div>
    <div id="excluded" class="small muted" style="margin-top:10px"></div>
  </section>

  <section class="two">
    <div class="card"><h2>What the data show</h2><dl class="facts">__FACTS__</dl></div>
    <div class="card"><h2>Warnings</h2><div id="warnings"></div></div>
  </section>

  <footer>__FOOTER__</footer>
</div>

<script type="application/json" id="dash-data">__DATA__</script>
<script>
(function () {
  "use strict";
  var D = JSON.parse(document.getElementById("dash-data").textContent);
  var NS = "http://www.w3.org/2000/svg";
  var state = { range: "recent", show80: true, show95: true, hover: -1 };

  // ---- formatting: the same rule the engine's text report uses
  function fmt(v) {
    var a = Math.abs(v);
    if (a >= 1000) return Math.round(v).toLocaleString("en-US");
    if (a >= 100) return v.toFixed(1);
    return String(Number(v.toPrecision(3)));
  }
  function axisFmt(v) { return v.toLocaleString("en-US", { maximumFractionDigits: 2 }); }
  function t(s) { return Date.parse(s.length <= 10 ? s + "T00:00:00Z" : s + "Z"); }
  var MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function dateLabel(ms, withTime) {
    var d = new Date(ms);
    var base = d.getUTCFullYear() + "-" + pad(d.getUTCMonth() + 1) + "-" + pad(d.getUTCDate());
    return withTime ? base + " " + pad(d.getUTCHours()) + ":00" : base;
  }
  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    if (attrs) for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }
  function sv(tag, attrs) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }

  // ---- series
  var H = D.history, F = D.forecast;
  var hT = H.ds.map(t), fT = F.ds.map(t);
  var hourly = fT.length > 1 && fT[1] - fT[0] < 86400000;
  var imputedSet = {}; H.imputed.forEach(function (i) { imputedSet[i] = true; });

  function niceTicks(lo, hi, n) {
    var span = hi - lo || 1, raw = span / n, mag = Math.pow(10, Math.floor(Math.log10(raw))), norm = raw / mag;
    var step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag, out = [];
    for (var v = Math.floor(lo / step) * step; v <= hi + step * 0.5; v += step) out.push(Number(v.toFixed(12)));
    return out;
  }
  function timeTicks(x0, x1, maxTicks) {
    var spanDays = (x1 - x0) / 86400000, out = [], d, i;
    if (spanDays > 45) {
      var steps = [1, 2, 3, 6, 12, 24, 60], months = spanDays / 30.4, s = 1;
      for (i = 0; i < steps.length; i++) { s = steps[i]; if (months / s <= maxTicks) break; }
      d = new Date(x0); var m = d.getUTCFullYear() * 12 + d.getUTCMonth();
      m = Math.ceil(m / s) * s;
      for (; ; m += s) {
        var ms = Date.UTC(Math.floor(m / 12), m % 12, 1);
        if (ms > x1) break;
        if (ms >= x0) out.push({ ms: ms, label: s >= 12 ? String(Math.floor(m / 12)) : MON[m % 12] + " " + Math.floor(m / 12) });
      }
    } else if (spanDays > 3) {
      var ds = [1, 2, 7, 14, 30], sd = 1;
      for (i = 0; i < ds.length; i++) { sd = ds[i]; if (spanDays / sd <= maxTicks) break; }
      var start = Math.ceil(x0 / 86400000 / sd) * sd * 86400000;
      for (var ms2 = start; ms2 <= x1; ms2 += sd * 86400000) { d = new Date(ms2); out.push({ ms: ms2, label: MON[d.getUTCMonth()] + " " + d.getUTCDate() }); }
    } else {
      var hs = [1, 3, 6, 12], sh = 1;
      for (i = 0; i < hs.length; i++) { sh = hs[i]; if (spanDays * 24 / sh <= maxTicks) break; }
      var st = Math.ceil(x0 / 3600000 / sh) * sh * 3600000;
      for (var ms3 = st; ms3 <= x1; ms3 += sh * 3600000) { d = new Date(ms3); out.push({ ms: ms3, label: pad(d.getUTCHours()) + ":00" }); }
    }
    return out;
  }

  // ---- main chart
  var plot = document.getElementById("plot");
  var tipEl = null;

  function visibleHistory() {
    if (state.range === "all") return 0;
    var keep = Math.max(5 * D.horizon, 90);
    return Math.max(0, hT.length - keep);
  }

  function drawChart() {
    var W = Math.max(280, plot.clientWidth), Ht = W < 560 ? 280 : 360;
    var m = { l: 50, r: 14, t: 10, b: 26 }, iw = W - m.l - m.r, ih = Ht - m.t - m.b;
    var from = visibleHistory();
    var x0 = hT[from], x1 = fT[fT.length - 1];
    var lo = Infinity, hi = -Infinity, i;
    for (i = from; i < hT.length; i++) { lo = Math.min(lo, H.y[i]); hi = Math.max(hi, H.y[i]); }
    for (i = 0; i < fT.length; i++) { lo = Math.min(lo, F.lo_80[i]); hi = Math.max(hi, F.hi_80[i]); }
    var wlo = lo, whi = hi;
    for (i = 0; i < fT.length; i++) { wlo = Math.min(wlo, F.lo_95[i]); whi = Math.max(whi, F.hi_95[i]); }
    if (state.show95 && (whi - wlo) <= 1.6 * ((hi - lo) || 1)) { lo = wlo; hi = whi; }
    var ticks = niceTicks(lo, hi, W < 560 ? 4 : 5), y0 = ticks[0], y1 = ticks[ticks.length - 1];
    function X(ms) { return m.l + (ms - x0) / (x1 - x0 || 1) * iw; }
    function Y(v) { return m.t + (1 - (v - y0) / (y1 - y0 || 1)) * ih; }

    var svg = sv("svg", { viewBox: "0 0 " + W + " " + Ht, role: "img", "aria-label":
      "Line chart of " + D.target + ": observed history and a " + D.horizon + "-period forecast with 80% and 95% prediction intervals." });
    svg.appendChild(sv("rect", { x: 0, y: 0, width: W, height: Ht, fill: "none" }));
    ticks.forEach(function (v) {
      svg.appendChild(sv("line", { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), stroke: "var(--grid)", "stroke-width": 1 }));
      var tx = sv("text", { x: m.l - 8, y: Y(v) + 4, "text-anchor": "end" }); tx.textContent = axisFmt(v); svg.appendChild(tx);
    });
    timeTicks(x0, x1, Math.max(3, Math.floor(iw / 90))).forEach(function (tk) {
      var tx = sv("text", { x: X(tk.ms), y: Ht - 6, "text-anchor": "middle" }); tx.textContent = tk.label; svg.appendChild(tx);
    });

    function band(lo_, hi_, fill) {
      var d = "M" + X(fT[0]) + " " + Y(hi_[0]);
      for (var k = 1; k < fT.length; k++) d += "L" + X(fT[k]) + " " + Y(hi_[k]);
      for (k = fT.length - 1; k >= 0; k--) d += "L" + X(fT[k]) + " " + Y(lo_[k]);
      svg.appendChild(sv("path", { d: d + "Z", fill: fill, stroke: "none" }));
    }
    if (state.show95) band(F.lo_95, F.hi_95, "var(--band95)");
    if (state.show80) band(F.lo_80, F.hi_80, "var(--band80)");

    var lastX = X(hT[hT.length - 1]);
    svg.appendChild(sv("line", { x1: lastX, x2: lastX, y1: m.t, y2: m.t + ih, stroke: "var(--ink-3)", "stroke-width": 1, "stroke-dasharray": "3 3" }));
    var fs = sv("text", { x: lastX - 6, y: m.t + 11, "text-anchor": "end" }); fs.textContent = "forecast starts"; svg.appendChild(fs);

    var hd = "";
    for (i = from; i < hT.length; i++) hd += (i === from ? "M" : "L") + X(hT[i]) + " " + Y(H.y[i]);
    svg.appendChild(sv("path", { d: hd, fill: "none", stroke: "var(--observed)", "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));
    var fd = "M" + lastX + " " + Y(H.y[H.y.length - 1]);
    for (i = 0; i < fT.length; i++) fd += "L" + X(fT[i]) + " " + Y(F.forecast[i]);
    svg.appendChild(sv("path", { d: fd, fill: "none", stroke: "var(--forecast)", "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));
    for (i = from; i < hT.length; i++) if (imputedSet[i]) {
      svg.appendChild(sv("circle", { cx: X(hT[i]), cy: Y(H.y[i]), r: 4, fill: "var(--surface)", stroke: "var(--observed)", "stroke-width": 2 }));
    }
    var ex = X(fT[fT.length - 1]), ey = Y(F.forecast[fT.length - 1]);
    svg.appendChild(sv("circle", { cx: ex, cy: ey, r: 5, fill: "var(--forecast)", stroke: "var(--surface)", "stroke-width": 2 }));
    var endLabel = sv("text", { x: ex - 8, y: ey - 10, "text-anchor": "end", style: "fill:var(--ink);font-weight:600" });
    endLabel.textContent = fmt(F.forecast[fT.length - 1]); svg.appendChild(endLabel);

    var cross = sv("g", { style: "display:none" });
    cross.appendChild(sv("line", { class: "cx", y1: m.t, y2: m.t + ih, stroke: "var(--ink-2)", "stroke-width": 1 }));
    cross.appendChild(sv("circle", { class: "cd", r: 5, stroke: "var(--surface)", "stroke-width": 2 }));
    svg.appendChild(cross);

    plot.textContent = "";
    plot.appendChild(svg);
    tipEl = el("div", { class: "tip", style: "display:none", role: "status" });
    plot.appendChild(tipEl);

    // ---- hover / keyboard: one list of points, nearest by x
    var pts = [];
    for (i = from; i < hT.length; i++) pts.push({ ms: hT[i], i: i, fc: false });
    for (i = 0; i < fT.length; i++) pts.push({ ms: fT[i], i: i, fc: true });
    function show(k) {
      if (k < 0 || k >= pts.length) return hide();
      state.hover = k;
      var p = pts[k], px = X(p.ms), v = p.fc ? F.forecast[p.i] : H.y[p.i];
      cross.style.display = "";
      cross.querySelector(".cx").setAttribute("x1", px); cross.querySelector(".cx").setAttribute("x2", px);
      var dot = cross.querySelector(".cd");
      dot.setAttribute("cx", px); dot.setAttribute("cy", Y(v)); dot.setAttribute("fill", p.fc ? "var(--forecast)" : "var(--observed)");
      tipEl.textContent = "";
      tipEl.appendChild(el("b", null, dateLabel(p.ms, hourly)));
      function row(a, b) { var r = el("div"); r.appendChild(el("span", null, a)); r.appendChild(el("span", null, b)); tipEl.appendChild(r); }
      if (p.fc) {
        row("Forecast", fmt(F.forecast[p.i]));
        row("80% interval", fmt(F.lo_80[p.i]) + " to " + fmt(F.hi_80[p.i]));
        row("95% interval", fmt(F.lo_95[p.i]) + " to " + fmt(F.hi_95[p.i]));
      } else {
        row(imputedSet[p.i] ? "Observed (filled)" : "Observed", fmt(H.y[p.i]));
      }
      tipEl.style.display = "";
      var tw = tipEl.offsetWidth, left = px + 14;
      if (left + tw > W - 4) left = px - tw - 14;
      tipEl.style.left = Math.max(4, left) + "px";
      tipEl.style.top = Math.max(4, Y(v) - tipEl.offsetHeight - 10) + "px";
    }
    function hide() { state.hover = -1; cross.style.display = "none"; tipEl.style.display = "none"; }
    function nearest(clientX) {
      var r = svg.getBoundingClientRect(), x = (clientX - r.left) * (W / r.width), best = 0, bd = Infinity;
      for (var k = 0; k < pts.length; k++) { var dd = Math.abs(X(pts[k].ms) - x); if (dd < bd) { bd = dd; best = k; } }
      return best;
    }
    plot.onpointermove = function (e) { show(nearest(e.clientX)); };
    plot.onpointerleave = hide;
    plot.onkeydown = function (e) {
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault();
        var cur = state.hover < 0 ? pts.length - fT.length : state.hover;
        show(Math.min(pts.length - 1, Math.max(0, cur + (e.key === "ArrowRight" ? 1 : -1))));
      } else if (e.key === "Escape") hide();
    };
    plot.onblur = hide;
  }

  function note() {
    var n = document.getElementById("plot-note"), parts = [];
    if (D.totalHistory > H.ds.length) parts.push("Showing the most recent " + H.ds.length + " of " + D.totalHistory + " observations.");
    if (H.imputed.length) parts.push("Hollow markers are periods that were filled in.");
    n.textContent = parts.join(" ");
    n.style.display = parts.length ? "" : "none";
  }

  function legend() {
    var box = document.getElementById("legend"); box.textContent = "";
    function item(label, kind, color, key) {
      var b = el("button", { type: "button" });
      if (key) { b.setAttribute("aria-pressed", String(state[key])); b.addEventListener("click", function () { state[key] = !state[key]; legend(); drawChart(); }); }
      else b.style.cursor = "default";
      var sw = el("span", { class: kind === "line" ? "key" : "sw" });
      if (kind === "line") sw.style.color = color; else sw.style.background = color;
      b.appendChild(sw); b.appendChild(document.createTextNode(label)); box.appendChild(b);
    }
    item("Observed", "line", "var(--observed)");
    item("Forecast", "line", "var(--forecast)");
    item("80% interval", "sw", "var(--band80)", "show80");
    item("95% interval", "sw", "var(--band95)", "show95");
  }

  document.querySelectorAll("#range button").forEach(function (b) {
    b.addEventListener("click", function () {
      state.range = b.getAttribute("data-range");
      document.querySelectorAll("#range button").forEach(function (o) { o.setAttribute("aria-pressed", String(o === b)); });
      drawChart();
    });
  });
  if (H.ds.length <= Math.max(5 * D.horizon, 90)) document.getElementById("range").style.display = "none";

  // ---- forecast table
  (function () {
    var tb = document.getElementById("fc-table"), head = el("tr");
    ["Date", "Forecast", "80% low", "80% high", "95% low", "95% high"].forEach(function (h) { head.appendChild(el("th", null, h)); });
    tb.appendChild(head);
    fT.forEach(function (ms, k) {
      var r = el("tr");
      [dateLabel(ms, hourly), fmt(F.forecast[k]), fmt(F.lo_80[k]), fmt(F.hi_80[k]), fmt(F.lo_95[k]), fmt(F.hi_95[k])].forEach(function (c) { r.appendChild(el("td", null, c)); });
      tb.appendChild(r);
    });
  })();

  // ---- model comparison
  (function () {
    var bars = document.getElementById("bars"), max = 0;
    D.models.forEach(function (m) { max = Math.max(max, m.score); });
    var unit = D.metric === "mase" ? "MASE" : "MAE";
    D.models.forEach(function (m) {
      var row = el("div", { class: "bar-row" + (m.name === D.selected ? " sel" : "") });
      var name = el("div", { class: "name" }, m.name);
      name.appendChild(el("small", null, m.kind + (m.name === D.selected ? ", selected" : "")));
      var track = el("div", { class: "track" });
      var fill = el("div", { class: "fill " + m.kind }); fill.style.width = (max > 0 ? Math.max(1, m.score / max * 100) * 0.72 : 1) + "%";
      track.appendChild(fill); track.appendChild(el("span", { class: "val" }, fmt(m.score)));
      row.appendChild(name); row.appendChild(track); bars.appendChild(row);
    });
    bars.setAttribute("aria-label", "Backtest " + unit + " by model, lower is better");

    // scores table
    var tb = document.getElementById("scores"), head = el("tr");
    ["Model", "Kind", D.metric === "mase" ? "MASE" : "MAE", "MAE", "RMSE", "sMAPE %", "80% coverage"].forEach(function (h, i) { head.appendChild(el("th", null, h)); });
    tb.appendChild(head);
    D.models.forEach(function (m) {
      var r = el("tr", m.name === D.selected ? { class: "sel" } : null);
      [m.name, m.kind, fmt(m.score), fmt(m.mae), fmt(m.rmse), fmt(m.smape), Math.round(m.cov80 * 100) + "%"].forEach(function (c) { r.appendChild(el("td", null, c)); });
      tb.appendChild(r);
    });
    var ex = document.getElementById("excluded");
    if (D.excluded.length) {
      ex.textContent = D.excluded.map(function (x) { return x.name + " (" + x.status + (x.reason ? ": " + x.reason : "") + ")"; }).join("  |  ");
    } else ex.style.display = "none";

    // per-window stability
    var sel = D.models.filter(function (m) { return m.name === D.selected; })[0];
    var cmp = D.models.filter(function (m) { return m.name === D.comparator; })[0];
    var wins = document.getElementById("wins"), key = document.getElementById("wins-key");
    document.getElementById("wins-title").textContent = cmp
      ? "Mean absolute error in each test window: " + sel.name + " against " + cmp.name + ". Lower is better."
      : "Mean absolute error in each test window. Lower is better.";
    var mx = 0; [sel, cmp].forEach(function (m) { if (m) m.windowMae.forEach(function (v) { mx = Math.max(mx, v); }); });
    sel.windowMae.forEach(function (_, k) {
      var col = el("div", { class: "win" }), pair = el("div", { class: "pair" });
      [sel, cmp].forEach(function (m) {
        if (!m) return;
        var bar = el("i", { title: m.name + ": " + fmt(m.windowMae[k]) });
        bar.style.height = (mx > 0 ? Math.max(1, m.windowMae[k] / mx * 100) : 1) + "%";
        bar.style.background = m.kind === "complex" ? "var(--complex)" : "var(--baseline)";
        if (m === sel) bar.style.boxShadow = "0 0 0 2px var(--surface), 0 0 0 3px var(--forecast)";
        pair.appendChild(bar);
      });
      col.appendChild(pair); col.appendChild(el("small", null, "Window " + (k + 1))); wins.appendChild(col);
    });
    [sel, cmp].forEach(function (m) {
      if (!m) return;
      var s = el("span", { class: m.kind === "complex" ? "c" : "b" }, m.name + (m === sel ? " (selected)" : "")); key.appendChild(s);
    });
    wins.setAttribute("role", "img");
    wins.setAttribute("aria-label", "Per-window mean absolute error for " + sel.name + (cmp ? " and " + cmp.name : ""));
  })();

  // ---- warnings
  (function () {
    var box = document.getElementById("warnings"), warn = D.warnings.filter(function (w) { return w.severity === "warn"; });
    var info = D.warnings.filter(function (w) { return w.severity !== "warn"; });
    function list(items) {
      var ul = el("ul", { class: "warns" });
      items.forEach(function (w) {
        var li = el("li"); li.appendChild(el("span", { class: "sev " + w.severity }, w.severity === "warn" ? "Warning" : "Note"));
        var d = el("div"); d.appendChild(el("div", null, w.message)); d.appendChild(el("div", { class: "code" }, w.code)); li.appendChild(d); ul.appendChild(li);
      });
      return ul;
    }
    if (!warn.length) box.appendChild(el("p", { class: "muted" }, "No warnings."));
    else box.appendChild(list(warn));
    if (info.length) {
      var det = el("details", { style: "margin-top:12px" }); det.appendChild(el("summary", null, info.length + (info.length === 1 ? " note" : " notes")));
      det.appendChild(list(info)); box.appendChild(det);
    }
  })();

  note(); legend(); drawChart();
  if (window.ResizeObserver) new ResizeObserver(function () { drawChart(); }).observe(plot);
  else window.addEventListener("resize", drawChart);
})();
</script>
"""
