"""Read a CSV into a clean, regular series.

Steps: read the file, detect the date/target/dimension columns, resolve which single series
to forecast, infer the observation frequency, and regularize onto a full calendar so that
missing timestamps can never silently shift seasonality.

Anything the data does not settle raises ``NeedsInputError`` (several reasonable readings) or
``RefusedError`` (not forecastable); nothing is guessed silently.
"""

from __future__ import annotations

import csv
import io
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from forecast.schema import (
    Ambiguity,
    ColumnCandidate,
    LoadReport,
    NeedsInputError,
    Notice,
    Option,
    RefusedError,
)

MAX_FILL_FRACTION = 0.10  # more missing than this and we refuse rather than invent data
DATE_PARSE_MIN = 0.95
NUMERIC_PARSE_MIN = 0.90
TARGET_CLEAR_MARGIN = 0.30  # top target must lead the runner-up by this much to be auto-chosen
DATE_CLEAR_MARGIN = 0.15
GRID_COVERAGE_MIN = 0.95  # share of timestamps that must sit on the inferred calendar
MAX_DIMENSION_VALUES = 200

NA_TOKENS = frozenset({"", "na", "n/a", "nan", "null", "none", "-", "--", "?"})
DATE_NAME_EXACT = ("date", "ds", "timestamp", "datetime", "time", "day", "dt", "period")
DATE_NAME_PARTS = ("date", "time", "day", "week", "month", "period", "year")
YEAR_NAMES = ("year", "yr", "fiscal_year")
TARGET_NAME_PARTS = (
    "sales", "revenue", "units", "demand", "quantity", "qty", "orders", "visits", "traffic",
    "sessions", "count", "volume", "amount", "value", "target", "users", "signups", "cases",
    "usage", "load", "mrr", "arr", "bookings", "pageviews", "views", "transactions",
)  # fmt: skip
TARGET_NAME_EXACT = ("y",)
COVARIATE_NAME_PARTS = (
    "price", "cost", "rate", "pct", "percent", "ratio", "temp", "discount", "lat", "lon",
    "index", "score", "margin",
)  # fmt: skip
WEAK_TARGET_NAME_PARTS = ("inventory", "stock")
ID_NAME = re.compile(r"(^|_)(id|code|key|sku)$|^id(_|$)", re.IGNORECASE)

FREQUENCY_NAMES = {
    "h": "hourly", "D": "daily", "B": "business-daily", "W": "weekly",
    "MS": "monthly", "ME": "monthly", "QS": "quarterly", "QE": "quarterly",
    "YS": "yearly", "YE": "yearly",
}  # fmt: skip
_WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
_NUMERIC_DATE = re.compile(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})(?:[ T].*)?$")


@dataclass
class LoadedSeries:
    """A single regular series. ``data`` has columns ``ds``, ``y`` and ``imputed``."""

    data: pd.DataFrame
    freq: str
    report: LoadReport


@dataclass
class ParsedDates:
    values: pd.Series
    rate: float
    ambiguous_order: bool = False


# --------------------------------------------------------------------------- reading


def read_table(path: str | Path) -> pd.DataFrame:
    """Read a delimited text file as strings (all typing is done explicitly, later)."""
    p = Path(path)
    if not p.is_file():
        raise RefusedError("FILE_UNREADABLE", f"File not found: {p}")
    raw = p.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    if not text.strip():
        raise RefusedError("FILE_UNREADABLE", f"File is empty: {p}")
    try:
        delimiter = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|").delimiter
    except csv.Error:
        delimiter = ","
    try:
        df = pd.read_csv(io.StringIO(text), sep=delimiter, dtype=str, keep_default_na=False)
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise RefusedError("FILE_UNREADABLE", f"Could not parse {p.name} as CSV: {exc}") from exc
    df.columns = [str(c).strip() for c in df.columns]
    for col in list(df.columns):
        values = df[col].str.strip()
        is_blank_name = col == "" or col.startswith("Unnamed:")
        if is_blank_name and (values == "").all() | values.str.fullmatch(r"\d+").all():
            df = df.drop(columns=col)  # pandas-style exported index
            continue
        df[col] = values.mask(values.str.lower().isin(NA_TOKENS))
    df = df.dropna(axis=1, how="all").dropna(axis=0, how="all").reset_index(drop=True)
    if df.empty or df.shape[1] < 2:
        raise RefusedError("FILE_UNREADABLE", "Need at least a date column and a value column.")
    return df


# --------------------------------------------------------------------------- numbers


def clean_numeric(s: pd.Series) -> tuple[pd.Series, int]:
    """Parse messy numeric text ('$1,234', '(5)', '1.234,5'). Returns (floats, n_invalid)."""
    t = s.astype("object")
    present = t.notna()
    u = t.where(present, "").astype(str).str.strip()
    u = u.str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    u = u.str.replace(r"[\s$€£¥]", "", regex=True)
    nonblank = u[u != ""]
    if len(nonblank):
        decimal_comma = (
            nonblank.str.contains(r"\d,\d{1,2}$").mean() >= 0.5
            and not nonblank.str.contains(r"\.\d{1,2}$").any()
        )
    else:
        decimal_comma = False
    u = (
        u.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        if decimal_comma
        else u.str.replace(",", "", regex=False)
    )
    values = pd.to_numeric(u.where(present & (u != "")), errors="coerce").astype(float)
    values[np.isinf(values)] = np.nan
    n_invalid = int((present & values.isna()).sum())
    return values, n_invalid


def _numeric_share(s: pd.Series) -> float:
    present = s.notna()
    if not present.any():
        return 0.0
    values, _ = clean_numeric(s)
    return float(values[present].notna().mean())


# --------------------------------------------------------------------------- dates


def parse_dates(s: pd.Series, order: Literal["dmy", "mdy"] | None = None) -> ParsedDates:
    """Parse a text column to datetimes; reports whether day/month order was a guess."""
    present = s.notna()
    text = s.where(present, "").astype(str).str.strip()
    ambiguous = False
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        parts = text[present].str.extract(_NUMERIC_DATE)
        if len(parts) and parts.notna().all(axis=1).mean() >= DATE_PARSE_MIN:
            first = pd.to_numeric(parts[0], errors="coerce")
            second = pd.to_numeric(parts[1], errors="coerce")
            if order is not None:
                dayfirst = order == "dmy"
            elif (first > 12).any():
                dayfirst = True
            elif (second > 12).any():
                dayfirst = False
            else:
                dayfirst = False
                ambiguous = bool((first != second).any())
            parsed = pd.to_datetime(
                text.where(present), dayfirst=dayfirst, errors="coerce", format="mixed"
            )
        else:
            parsed = pd.to_datetime(text.where(present), errors="coerce", format="ISO8601")
            if parsed[present].notna().mean() < DATE_PARSE_MIN:
                alt = pd.to_datetime(text.where(present), errors="coerce", format="mixed")
                if alt[present].notna().mean() > parsed[present].notna().mean():
                    parsed = alt
    if getattr(parsed.dtype, "tz", None) is not None:
        parsed = parsed.dt.tz_localize(None)
    rate = float(parsed[present].notna().mean()) if present.any() else 0.0
    return ParsedDates(values=parsed, rate=rate, ambiguous_order=ambiguous)


def _year_to_dates(s: pd.Series) -> pd.Series | None:
    values, _ = clean_numeric(s)
    ok = values.dropna()
    if len(ok) and ((ok % 1 == 0) & ok.between(1800, 2200)).all():
        return pd.to_datetime(values.dropna().astype(int).astype(str) + "-01-01").reindex(s.index)
    return None


def _name_hint(name: str, exact: tuple[str, ...], parts: tuple[str, ...]) -> float:
    low = name.lower().strip()
    if low in exact:
        return 1.0
    return 0.6 if any(p in low for p in parts) else 0.0


def detect_date_candidates(df: pd.DataFrame) -> list[ColumnCandidate]:
    out = []
    for col in df.columns:
        s = df[col]
        reasons = []
        if _numeric_share(s) >= NUMERIC_PARSE_MIN:
            if col.lower() in YEAR_NAMES and _year_to_dates(s) is not None:
                out.append(ColumnCandidate(name=col, score=0.9, reasons=["integer years"]))
            continue  # numbers are not dates (a price of 1999 is not the year 1999)
        parsed = parse_dates(s)
        if parsed.rate < DATE_PARSE_MIN:
            continue
        hint = _name_hint(col, DATE_NAME_EXACT, DATE_NAME_PARTS)
        values = parsed.values.dropna()
        mono = bool(values.is_monotonic_increasing)
        score = 0.5 * parsed.rate + 0.3 * hint + 0.1 * mono + 0.1 * float(values.is_unique)
        reasons = [f"{parsed.rate:.0%} parse as dates"]
        if hint:
            reasons.append("name looks like a date")
        if mono:
            reasons.append("sorted")
        out.append(ColumnCandidate(name=col, score=round(score, 3), reasons=reasons))
    return sorted(out, key=lambda c: -c.score)


def _is_idlike(col: str, values: pd.Series) -> bool:
    """Identifier columns are recognised by name only; value patterns are too easily a real series."""
    return bool(ID_NAME.search(col)) and bool(len(values.dropna()))


def detect_target_candidates(df: pd.DataFrame, exclude: set[str]) -> list[ColumnCandidate]:
    out = []
    for col in df.columns:
        if col in exclude or _numeric_share(df[col]) < NUMERIC_PARSE_MIN:
            continue
        values, _ = clean_numeric(df[col])
        if values.notna().sum() == 0 or _is_idlike(col, values):
            continue
        low = col.lower()
        score, reasons = 0.5, []
        if low in TARGET_NAME_EXACT or any(p in low for p in TARGET_NAME_PARTS):
            score += 0.4
            reasons.append("name looks like a measured quantity")
        if any(p in low for p in COVARIATE_NAME_PARTS):
            score -= 0.3
            reasons.append("name looks like a covariate")
        if any(p in low for p in WEAK_TARGET_NAME_PARTS):
            score -= 0.1
            reasons.append("stock/level column")
        out.append(ColumnCandidate(name=col, score=round(score, 3), reasons=reasons))
    return sorted(out, key=lambda c: -c.score)


def detect_dimensions(df: pd.DataFrame, exclude: set[str]) -> list[str]:
    """Columns that split the data into several series (store, product, region...)."""
    dims = []
    for col in df.columns:
        if col in exclude:
            continue
        nunique = df[col].nunique(dropna=True)
        if nunique < 1 or nunique > min(MAX_DIMENSION_VALUES, 0.5 * len(df)):
            continue
        numeric = _numeric_share(df[col]) >= NUMERIC_PARSE_MIN
        if not numeric or ID_NAME.search(col):
            dims.append(col)
    return dims


# --------------------------------------------------------------------------- frequency


def infer_frequency(ts: pd.DatetimeIndex) -> tuple[str, int]:
    """Return (pandas alias, n_missing_timestamps) for a sorted, unique DatetimeIndex."""
    if len(ts) < 3:
        raise RefusedError(
            "INSUFFICIENT_DATA", "Need at least 3 distinct timestamps to infer a frequency."
        )
    alias = pd.infer_freq(ts) if len(ts) >= 3 else None
    if alias is None:
        alias = _freq_from_spacing(ts)
    if alias is None:
        raise RefusedError(
            "IRREGULAR_SAMPLING",
            "Timestamps are not evenly spaced on any supported calendar "
            "(hourly, daily, business-daily, weekly, monthly, quarterly, yearly).",
        )
    alias = {"H": "h", "M": "ME", "Q": "QE-DEC", "A": "YE-DEC", "Y": "YE-DEC"}.get(alias, alias)
    if alias.split("-")[0] not in FREQUENCY_NAMES:
        raise RefusedError("IRREGULAR_SAMPLING", f"Unsupported observation frequency '{alias}'.")
    grid = pd.date_range(ts[0], ts[-1], freq=alias)
    on_grid = ts.isin(grid)
    if on_grid.mean() < GRID_COVERAGE_MIN:
        raise RefusedError(
            "IRREGULAR_SAMPLING",
            f"Only {on_grid.mean():.0%} of timestamps fall on a regular {alias} calendar.",
            frequency=alias,
        )
    return alias, int(len(grid) - on_grid.sum())


def _freq_from_spacing(ts: pd.DatetimeIndex) -> str | None:
    step = pd.Series(ts).diff().dropna().median()
    days = step.total_seconds() / 86400
    first_month = _MONTHS[ts[0].month - 1]
    starts = bool((ts.day == 1).all())
    ends = bool(ts.is_month_end.all())
    if abs(days - 1 / 24) < 1e-9:
        return "h"
    if abs(days - 1) < 1e-9:
        return "B" if not (ts.dayofweek >= 5).any() and len(ts) >= 10 else "D"
    if abs(days - 7) < 1e-9:
        mode_day = int(pd.Series(ts.dayofweek).mode().iloc[0])
        return f"W-{_WEEKDAYS[mode_day][:3]}"
    if 28 <= days <= 31:
        return "MS" if starts else "ME" if ends else None
    if 89 <= days <= 92:
        return f"QS-{first_month}" if starts else f"QE-{first_month}" if ends else None
    if 364 <= days <= 366:
        return f"YS-{first_month}" if starts else f"YE-{first_month}" if ends else None
    return None


# --------------------------------------------------------------------------- series


def _options_for_series(work: pd.DataFrame, dims: list[str]) -> list[Option]:
    options = [
        Option(label="Total across everything (sum)", cli_args=["--agg", "sum"],
               description="Add the target up for each date."),
        Option(label="Average across everything (mean)", cli_args=["--agg", "mean"],
               description="Average the target for each date."),
    ]  # fmt: skip
    for dim in dims:
        values = sorted(work[dim].dropna().unique().tolist())
        options.append(
            Option(
                label=f"One {dim} (n={len(values)})",
                cli_args=["--where", f"{dim}=<value>"],
                description="Forecast a single slice; repeat --where to fix several columns.",
                values=values[:20],
            )
        )
    return options


def _select_series(
    work: pd.DataFrame,
    dims: list[str],
    where: dict[str, str] | None,
    agg: Literal["sum", "mean"] | None,
    notices: list[Notice],
) -> pd.DataFrame:
    """Reduce (ds, y, *dims) rows to one row per timestamp, or raise NeedsInputError."""
    lookup = {c.lower(): c for c in work.columns}
    for key, value in (where or {}).items():
        col = lookup.get(key.lower())
        if col is None or col not in dims:
            raise RefusedError(
                "BAD_ARGUMENT",
                f"--where column '{key}' is not a dimension column.",
                dimensions=dims,
            )
        work = work[work[col].astype(str).str.strip() == str(value).strip()]
        if work.empty:
            raise RefusedError("WHERE_NO_MATCH", f"No rows where {col} = {value}.")
    exact = work.drop_duplicates()
    if len(exact) < len(work):
        notices.append(Notice(code="DUPLICATE_ROWS_DROPPED", severity="info",
                              message=f"Dropped {len(work) - len(exact)} exact duplicate rows.",
                              details={"n": len(work) - len(exact)}))  # fmt: skip
        work = exact
    if not work["ds"].duplicated().any():
        return work[["ds", "y"]]
    active = [d for d in dims if work[d].nunique(dropna=True) > 1]
    if agg is None:
        if active:
            question = (
                f"The data has several series (by {', '.join(active)}). "
                "Which one should be forecast?"
            )
            raise NeedsInputError(
                [
                    Ambiguity(
                        kind="series", question=question, options=_options_for_series(work, active)
                    )
                ]
            )
        raise NeedsInputError([
            Ambiguity(
                kind="duplicates",
                question="Several rows share the same timestamp with different values. How should they be combined?",
                options=[Option(label="Sum them", cli_args=["--agg", "sum"]),
                         Option(label="Average them", cli_args=["--agg", "mean"])],
            )
        ])  # fmt: skip
    grouped = work.groupby("ds")["y"]
    counts = grouped.size()
    if active and counts.nunique() > 1:
        notices.append(Notice(code="UNBALANCED_PANEL", severity="warn",
                              message="Dates have differing numbers of contributing rows, so totals may dip "
                                      "where a slice is missing.",
                              details={"min_rows": int(counts.min()), "max_rows": int(counts.max())}))  # fmt: skip
    out = grouped.sum(min_count=1) if agg == "sum" else grouped.mean()
    return out.rename("y").reset_index()


def _longest_run(mask: np.ndarray) -> int:
    best = run = 0
    for flag in mask:
        run = run + 1 if flag else 0
        best = max(best, run)
    return best


def regularize(
    data: pd.DataFrame, freq: str, fill: Literal["interpolate", "zero"], notices: list[Notice]
) -> pd.DataFrame:
    """Put (ds, y) on the full calendar, trim empty edges, fill gaps per policy."""
    data = data.sort_values("ds").drop_duplicates("ds")
    grid = pd.date_range(data["ds"].iloc[0], data["ds"].iloc[-1], freq=freq)
    dropped = int((~data["ds"].isin(grid)).sum())
    if dropped:
        notices.append(Notice(code="OFF_CALENDAR_DROPPED", severity="warn",
                              message=f"Dropped {dropped} observations that are not on the {freq} calendar.",
                              details={"n": dropped}))  # fmt: skip
    full = data.set_index("ds")["y"].reindex(grid)
    valid = full.notna().to_numpy()
    if not valid.any():
        raise RefusedError("INSUFFICIENT_DATA", "The target has no numeric values.")
    first, last = np.argmax(valid), len(valid) - 1 - np.argmax(valid[::-1])
    if first or last < len(valid) - 1:
        notices.append(Notice(code="EDGES_TRIMMED", severity="info",
                              message="Trimmed leading/trailing periods with no value.",
                              details={"leading": int(first), "trailing": int(len(valid) - 1 - last)}))  # fmt: skip
    full = full.iloc[first : last + 1]
    missing = full.isna().to_numpy()
    fraction = float(missing.mean())
    if fraction > MAX_FILL_FRACTION:
        raise RefusedError(
            "MISSING_DATA_HIGH",
            f"{fraction:.0%} of periods have no value (limit {MAX_FILL_FRACTION:.0%}); "
            "filling that much would mean inventing the forecast's inputs.",
            fraction=round(fraction, 4),
        )
    filled = (
        full.interpolate(method="linear", limit_area="inside")
        if fill == "interpolate"
        else full.fillna(0.0)
    )
    out = pd.DataFrame({"ds": filled.index, "y": filled.to_numpy(), "imputed": missing})
    if missing.any():
        notices.append(Notice(code="MISSING_FILLED", severity="warn" if fraction > 0.02 else "info",
                              message=f"Filled {int(missing.sum())} missing periods by {fill}.",
                              details={"n": int(missing.sum()), "fraction": round(fraction, 4),
                                       "longest_gap": _longest_run(missing)}))  # fmt: skip
    return out.reset_index(drop=True)


# --------------------------------------------------------------------------- entry point


def load_series(
    path: str | Path,
    *,
    date: str | None = None,
    target: str | None = None,
    where: dict[str, str] | None = None,
    agg: Literal["sum", "mean"] | None = None,
    fill: Literal["interpolate", "zero"] = "interpolate",
    date_order: Literal["dmy", "mdy"] | None = None,
) -> LoadedSeries:
    df = read_table(path)
    n_rows_raw = len(df)
    columns = {c.lower(): c for c in df.columns}
    notices: list[Notice] = []
    ambiguities: list[Ambiguity] = []

    # ---- date column
    date_candidates = detect_date_candidates(df)
    if date is not None:
        if date.lower() not in columns:
            raise RefusedError(
                "BAD_ARGUMENT", f"--date column '{date}' not found.", columns=list(df.columns)
            )
        date_col = columns[date.lower()]
    else:
        if not date_candidates:
            raise RefusedError(
                "NO_DATE_COLUMN",
                "No column looks like dates or timestamps.",
                columns=list(df.columns),
            )
        date_col = date_candidates[0].name
        if (
            len(date_candidates) > 1
            and date_candidates[0].score - date_candidates[1].score < DATE_CLEAR_MARGIN
        ):
            ambiguities.append(Ambiguity(
                kind="date", question="Several columns look like dates. Which is the time axis?",
                options=[Option(label=c.name, cli_args=["--date", c.name]) for c in date_candidates[:5]],
            ))  # fmt: skip

    # ---- target column
    target_candidates = detect_target_candidates(df, exclude={date_col})
    if target is not None:
        if target.lower() not in columns or columns[target.lower()] == date_col:
            raise RefusedError(
                "BAD_ARGUMENT", f"--target column '{target}' not found.", columns=list(df.columns)
            )
        target_col = columns[target.lower()]
    else:
        if not target_candidates:
            raise RefusedError(
                "NO_TARGET_COLUMN", "No numeric column to forecast.", columns=list(df.columns)
            )
        target_col = target_candidates[0].name
        if (
            len(target_candidates) > 1
            and target_candidates[0].score - target_candidates[1].score < TARGET_CLEAR_MARGIN
        ):
            ambiguities.append(Ambiguity(
                kind="target", question="Several numeric columns could be forecast. Which one?",
                options=[Option(label=c.name, cli_args=["--target", c.name]) for c in target_candidates[:6]],
            ))  # fmt: skip
        elif len(target_candidates) > 1:
            notices.append(Notice(code="TARGET_AUTO_SELECTED", severity="info",
                                  message=f"Chose '{target_col}' as the target.",
                                  details={"alternatives": [c.name for c in target_candidates[1:]]}))  # fmt: skip

    # ---- parse date + target
    if date_col.lower() in YEAR_NAMES and _numeric_share(df[date_col]) >= NUMERIC_PARSE_MIN:
        ds = _year_to_dates(df[date_col])
        parsed = ParsedDates(values=ds, rate=1.0)  # type: ignore[arg-type]
    else:
        parsed = parse_dates(df[date_col], date_order)
    if parsed.rate < DATE_PARSE_MIN:
        raise RefusedError(
            "DATE_PARSE_FAILED", f"Only {parsed.rate:.0%} of '{date_col}' values parse as dates."
        )
    if parsed.ambiguous_order:
        ambiguities.append(Ambiguity(
            kind="date_format",
            question=f"Dates in '{date_col}' like 03/04/2024 are ambiguous. Day first or month first?",
            options=[Option(label="Day first (31/12/2024)", cli_args=["--date-order", "dmy"]),
                     Option(label="Month first (12/31/2024)", cli_args=["--date-order", "mdy"])],
        ))  # fmt: skip
    y, n_invalid = clean_numeric(df[target_col])
    if n_invalid:
        notices.append(Notice(code="INVALID_VALUES", severity="warn",
                              message=f"{n_invalid} non-numeric values in '{target_col}' were treated as missing.",
                              details={"n": n_invalid}))  # fmt: skip

    dims = detect_dimensions(df, exclude={date_col, target_col})
    work = pd.DataFrame({"ds": parsed.values, "y": y})
    for d in dims:
        work[d] = df[d]
    bad_dates = int(work["ds"].isna().sum())
    if bad_dates:
        notices.append(Notice(code="DATE_ROWS_DROPPED", severity="warn",
                              message=f"Dropped {bad_dates} rows with unparseable dates.", details={"n": bad_dates}))  # fmt: skip
        work = work.dropna(subset=["ds"])

    try:
        series = _select_series(work, dims, where, agg, notices)
    except NeedsInputError as exc:
        raise NeedsInputError(ambiguities + exc.ambiguities) from None
    if ambiguities:
        raise NeedsInputError(ambiguities)

    # ---- frequency + calendar
    ts = pd.DatetimeIndex(sorted(series["ds"].unique()))
    freq, n_missing_ts = infer_frequency(ts)
    data = regularize(series, freq, fill, notices)

    n_missing_values = int(series["y"].isna().sum())
    imputed = data["imputed"].to_numpy()
    report = LoadReport(
        file=str(path),
        date_column=date_col,
        target_column=target_col,
        frequency=freq,
        frequency_name=FREQUENCY_NAMES[freq.split("-")[0]],
        n_rows_raw=n_rows_raw,
        n_obs=len(data),
        start=data["ds"].iloc[0].isoformat(),
        end=data["ds"].iloc[-1].isoformat(),
        n_missing_timestamps=n_missing_ts,
        n_missing_values=n_missing_values,
        n_imputed=int(imputed.sum()),
        longest_gap=_longest_run(imputed),
        fill_policy=fill,
        where=dict(where or {}),
        agg=agg,
        target_candidates=target_candidates,
        dimension_columns=dims,
        notices=notices,
    )
    return LoadedSeries(data=data, freq=freq, report=report)
