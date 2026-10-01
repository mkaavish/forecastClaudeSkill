"""Data contracts shared by the engine, the CLI and the Claude skill.

Everything the skill reads is defined here, so Claude consumes validated JSON rather than
free text. JSON Schemas are exported to ``schemas/`` (``python -m forecast.schema schemas``).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1"

Severity = Literal["info", "warn"]

RefusalCode = Literal[
    "FILE_UNREADABLE",
    "BAD_ARGUMENT",
    "NO_DATE_COLUMN",
    "NO_TARGET_COLUMN",
    "DATE_PARSE_FAILED",
    "INSUFFICIENT_DATA",
    "IRREGULAR_SAMPLING",
    "MISSING_DATA_HIGH",
    "WHERE_NO_MATCH",
    "HORIZON_TOO_LONG",
    "CONSTANT_SERIES",
]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Notice(_Model):
    """A non-fatal observation about the data or the run (the ``warnings`` list)."""

    code: str
    severity: Severity
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class Option(_Model):
    """One way to resolve an ambiguity, expressed as CLI arguments Claude can pass back."""

    label: str
    cli_args: list[str]
    description: str = ""
    values: list[str] | None = None  # sample of valid values when cli_args holds a <value> slot


class Ambiguity(_Model):
    kind: Literal["date", "date_format", "target", "series", "duplicates"]
    question: str
    options: list[Option]


class ColumnCandidate(_Model):
    name: str
    score: float
    reasons: list[str] = Field(default_factory=list)


class LoadReport(_Model):
    """What loading did to the raw file; the ``input`` section of later reports."""

    schema_version: str = SCHEMA_VERSION
    file: str
    date_column: str
    target_column: str
    frequency: str
    frequency_name: str
    n_rows_raw: int
    n_obs: int
    start: str
    end: str
    n_missing_timestamps: int
    n_missing_values: int
    n_imputed: int
    longest_gap: int
    fill_policy: Literal["interpolate", "zero"]
    where: dict[str, str] = Field(default_factory=dict)
    agg: Literal["sum", "mean"] | None = None
    target_candidates: list[ColumnCandidate] = Field(default_factory=list)
    dimension_columns: list[str] = Field(default_factory=list)
    notices: list[Notice] = Field(default_factory=list)


class Stats(_Model):
    n: int
    mean: float
    std: float
    min: float
    q25: float
    median: float
    q75: float
    max: float
    zero_fraction: float
    n_negative: int
    cv: float | None  # std / |mean|; None when the mean is 0


class Intermittency(_Model):
    applicable: bool  # only defined for non-negative series
    adi: float | None  # average demand interval: periods per non-zero observation
    cv2: float | None  # squared coefficient of variation of non-zero values
    demand_class: Literal["smooth", "erratic", "intermittent", "lumpy"] | None
    zero_heavy: bool


class Outlier(_Model):
    ds: str
    value: float
    robust_z: float


class OutlierSummary(_Model):
    method: str
    n_outliers: int
    fraction: float
    top: list[Outlier]  # largest |z| first; flagged only, never removed


class Trend(_Model):
    direction: Literal["positive", "negative", "none", "insufficient_data"]
    slope_per_period: float | None  # Theil-Sen
    relative_change: float | None  # slope * (n - 1) / |median|
    p_value: float | None  # Kendall tau test of the (seasonally adjusted) series against time
    drift_p_value: (
        float | None
    )  # t-test that first differences have non-zero mean; guards against random walks


class SeasonalityCandidate(_Model):
    period: int
    cycles: float  # complete cycles available
    tested: bool
    strength: float | None  # Hyndman STL seasonal strength, 0..1 (effect size)
    p_value: float | None  # F-test of detrended values across seasonal positions
    detected: bool
    independent: bool | None = (
        None  # for non-primary detected periods: still significant after removing the primary
    )
    note: str = ""


class Seasonality(_Model):
    candidates: list[SeasonalityCandidate]
    season_length: int  # strongest detected period, or 1
    multiple: bool  # a second period is significant after removing the primary one
    trend_strength: float | None


class ProfileReport(_Model):
    schema_version: str = SCHEMA_VERSION
    status: Literal["ok"] = "ok"
    input: LoadReport
    stats: Stats
    constant: bool
    near_constant: bool
    intermittency: Intermittency
    outliers: OutlierSummary
    trend: Trend
    seasonality: Seasonality
    warnings: list[Notice] = Field(default_factory=list)


class BacktestWindow(_Model):
    """One rolling-origin split in observation-index space (end indices are exclusive)."""

    index: int
    train_end: int  # train = [0, train_end); expanding window
    test_start: int  # always == train_end
    test_end: int


class BacktestPlan(_Model):
    horizon: int  # horizon the user wants forecast
    backtest_horizon: int  # horizon actually evaluated; < horizon when history is short
    n_windows: int
    step: int  # == backtest_horizon: test blocks do not overlap
    min_train: int
    season_length: int
    shortened: bool
    windows: list[BacktestWindow]
    notices: list[Notice] = Field(default_factory=list)


class NeedsInputReport(_Model):
    schema_version: str = SCHEMA_VERSION
    status: Literal["needs_input"] = "needs_input"
    ambiguities: list[Ambiguity]


class RefusalReport(_Model):
    schema_version: str = SCHEMA_VERSION
    status: Literal["refused"] = "refused"
    code: RefusalCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class RefusedError(Exception):
    """The data cannot be forecast (or the request is invalid); maps to status ``refused``."""

    def __init__(self, code: RefusalCode, message: str, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def report(self) -> RefusalReport:
        return RefusalReport(code=self.code, message=self.message, details=self.details)


class NeedsInputError(Exception):
    """More than one reasonable interpretation exists; maps to status ``needs_input``."""

    def __init__(self, ambiguities: list[Ambiguity]) -> None:
        super().__init__("; ".join(a.question for a in ambiguities))
        self.ambiguities = ambiguities

    def report(self) -> NeedsInputReport:
        return NeedsInputReport(ambiguities=self.ambiguities)


CONTRACTS: dict[str, type[BaseModel]] = {
    "load_report": LoadReport,
    "profile": ProfileReport,
    "needs_input": NeedsInputReport,
    "refusal": RefusalReport,
}


def export_schemas(directory: str | Path) -> list[Path]:
    """Write one JSON Schema per contract (stable ordering, trailing newline)."""
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name, model in CONTRACTS.items():
        path = out / f"{name}.schema.json"
        path.write_text(json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n")
        written.append(path)
    return written


if __name__ == "__main__":
    for p in export_schemas(sys.argv[1] if len(sys.argv) > 1 else "schemas"):
        print(p)
