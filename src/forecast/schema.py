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
