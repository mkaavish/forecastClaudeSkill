// Schematic of an expanding-window rolling-origin backtest.
const ROWS = 4;
const H = 4; // test window length, in units
const START = 10; // initial training length
const UNIT = 22;
const ROW_H = 30;
const LEFT = 72;

export function BacktestDiagram() {
  const width = LEFT + (START + ROWS * H + 2) * UNIT;
  const height = ROWS * ROW_H + 44;
  return (
    <figure>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Four backtest windows. Each trains on all history before a cutoff and is tested on the next stretch of the series."
        className="w-full"
      >
        {Array.from({ length: ROWS }, (_, i) => {
          const y = i * ROW_H + 6;
          const trainW = (START + i * H) * UNIT;
          return (
            <g key={i}>
              <text x={0} y={y + 14} className="fill-subtle font-mono" fontSize="11">
                window {i + 1}
              </text>
              <rect x={LEFT} y={y} width={trainW} height={18} rx={2} className="fill-subtle/35" />
              <rect
                x={LEFT + trainW + 2}
                y={y}
                width={H * UNIT - 2}
                height={18}
                rx={2}
                className="fill-accent"
              />
            </g>
          );
        })}
        <line
          x1={LEFT}
          x2={width - 8}
          y1={ROWS * ROW_H + 12}
          y2={ROWS * ROW_H + 12}
          className="stroke-subtle"
          strokeWidth="1"
        />
        <text x={width - 8} y={ROWS * ROW_H + 30} textAnchor="end" className="fill-subtle font-mono" fontSize="11">
          time →
        </text>
      </svg>
      <figcaption className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 font-mono text-xs text-subtle">
        <span className="inline-flex items-center gap-2">
          <span aria-hidden className="h-2.5 w-4 rounded-sm bg-subtle/35" /> train on history
        </span>
        <span className="inline-flex items-center gap-2">
          <span aria-hidden className="h-2.5 w-4 rounded-sm bg-accent" /> score on held-out horizon
        </span>
        <span>schematic</span>
      </figcaption>
    </figure>
  );
}
