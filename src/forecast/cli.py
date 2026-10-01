"""Command-line interface.

``forecast profile FILE`` prints a JSON document to stdout. Its ``status`` field tells the
caller what happened: ``ok`` (a profile), ``needs_input`` (ambiguities to resolve) or
``refused`` (not forecastable / invalid request).

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
    p.add_argument("--output", type=Path, help="directory to also write result files into")
    return p


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forecast", description="Statistically backtested forecasting."
    )
    parser.add_argument("--version", action="version", version=f"forecast {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("profile", parents=[_data_options()], help="profile a dataset (no forecasting)")
    return parser


def _emit(report, output: Path | None, filename: str) -> None:
    text = report.model_dump_json(indent=2)
    print(text)
    if output is not None:
        output.mkdir(parents=True, exist_ok=True)
        (output / filename).write_text(text + "\n")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        loaded = load_series(
            args.file,
            date=args.date,
            target=args.target,
            where=dict(args.where),
            agg=args.agg,
            fill=args.fill,
            date_order=args.date_order,
        )
        report = profile_series(loaded)
    except NeedsInputError as exc:
        _emit(exc.report(), args.output, "needs_input.json")
        return EXIT_NEEDS_INPUT
    except RefusedError as exc:
        _emit(exc.report(), args.output, "refusal.json")
        return EXIT_REFUSED
    _emit(report, args.output, "profile.json")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
