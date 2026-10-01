"""Command-line interface.

    forecast FILE [--horizon N] [--target COL] ...     # same as `forecast run FILE`
    forecast run FILE      full analysis; writes result files, prints a short summary (or JSON)
    forecast profile FILE  profile only; prints JSON

Every JSON document carries a ``status``: ``ok`` / ``ok_with_warnings``, ``needs_input``
(ambiguities to resolve) or ``refused`` (not forecastable / invalid request).

Exit codes: 0 ok, 1 internal error, 2 usage error, 3 needs_input, 4 refused.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from forecast import __version__
from forecast.loading import load_series
from forecast.profile import profile_series
from forecast.schema import NeedsInputError, RefusedError

EXIT_OK, EXIT_USAGE, EXIT_NEEDS_INPUT, EXIT_REFUSED = 0, 2, 3, 4
COMMANDS = ("profile", "run")


def _where_pair(text: str) -> tuple[str, str]:
    key, sep, value = text.partition("=")
    if not sep or not key.strip():
        raise argparse.ArgumentTypeError(f"expected COLUMN=VALUE, got '{text}'")
    return key.strip(), value.strip()


def _data_options() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("file", help="CSV file with a date column and a numeric column")
    p.add_argument("--target", help="column to forecast (inferred when obvious)")
    p.add_argument("--date", help="date/time column (inferred when obvious)")
    p.add_argument("--where", action="append", type=_where_pair, default=[], metavar="COL=VALUE",
                   help="keep only rows where COL equals VALUE (repeatable)")  # fmt: skip
    p.add_argument("--agg", choices=["sum", "mean"], help="combine rows that share a timestamp")
    p.add_argument("--fill", choices=["interpolate", "zero"], default="interpolate",
                   help="how to fill missing periods (default: interpolate)")  # fmt: skip
    p.add_argument(
        "--date-order", choices=["dmy", "mdy"], help="resolve ambiguous dates like 03/04/2024"
    )
    p.add_argument(
        "--output",
        type=Path,
        help="directory for result files (run: default ./forecast-output/<name>)",
    )
    return p


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forecast", description="Statistically backtested forecasting."
    )
    parser.add_argument("--version", action="version", version=f"forecast {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser(
        "profile", parents=[_data_options()], help="profile a dataset (no forecasting); prints JSON"
    )
    run = sub.add_parser(
        "run", parents=[_data_options()], help="profile, backtest, select, forecast"
    )
    run.add_argument(
        "--horizon", type=int, help="periods to forecast (default depends on the frequency)"
    )
    run.add_argument(
        "--json", action="store_true", help="print the full result as JSON instead of a summary"
    )
    return parser


def _route(argv: list[str]) -> list[str]:
    """`forecast FILE ...` means `forecast run FILE ...`."""
    if argv and argv[0] not in COMMANDS and argv[0] not in ("-h", "--help", "--version"):
        return ["run", *argv]
    return argv


def _emit_json(report, output: Path | None, filename: str) -> None:
    text = report.model_dump_json(indent=2)
    print(text)
    if output is not None:
        output.mkdir(parents=True, exist_ok=True)
        (output / filename).write_text(text + "\n")


def _print_needs_input(exc: NeedsInputError) -> None:
    print("More information is needed before forecasting:")
    for amb in exc.ambiguities:
        print(f"\n- {amb.question}")
        for opt in amb.options:
            hint = f"  ({' '.join(opt.cli_args)})"
            print(f"    * {opt.label}{hint}")


def _print_summary(result) -> None:
    f, sel = result.forecast, result.selection
    print(f"Forecast of '{result.input.target_column}': {f.horizon} {result.input.frequency_name} periods "
          f"({f.start[:10]} to {f.end[:10]})")  # fmt: skip
    print(f"Model: {f.model} - {sel.explanation}")
    change = (
        ""
        if f.change_vs_prior is None
        else f" ({f.change_vs_prior:+.1%} vs the previous {f.horizon} periods)"
    )
    print(f"Total over the horizon: {f.total:,.6g}{change}")
    for w in result.warnings:
        if w.severity == "warn":
            print(f"Warning [{w.code}]: {w.message}")
    print(f"Files: {result.artifacts.directory}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(_route(list(sys.argv[1:] if argv is None else argv)))
    as_json = args.command == "profile" or args.json
    try:
        if args.command == "profile":
            loaded = load_series(args.file, date=args.date, target=args.target, where=dict(args.where),
                                 agg=args.agg, fill=args.fill, date_order=args.date_order)  # fmt: skip
            _emit_json(profile_series(loaded), args.output, "profile.json")
            return EXIT_OK

        from forecast.outputs import write_artifacts
        from forecast.pipeline import run_forecast

        outcome = run_forecast(args.file, horizon=args.horizon, date=args.date, target=args.target,
                               where=dict(args.where), agg=args.agg, fill=args.fill, date_order=args.date_order)  # fmt: skip
        out_dir = args.output or Path("forecast-output") / Path(args.file).stem
        result = write_artifacts(outcome, out_dir)
        if args.json:
            print(result.model_dump_json(indent=2))
        else:
            _print_summary(result)
        return EXIT_OK
    except NeedsInputError as exc:
        if as_json:
            _emit_json(exc.report(), args.output, "needs_input.json")
        else:
            _print_needs_input(exc)
        return EXIT_NEEDS_INPUT
    except RefusedError as exc:
        if as_json:
            _emit_json(exc.report(), args.output, "refusal.json")
        else:
            print(f"Cannot forecast ({exc.code}): {exc.message}")
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
