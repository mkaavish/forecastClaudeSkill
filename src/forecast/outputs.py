"""Writers for result files.

A run directory contains:

* ``result.json``   - the validated RunResult (everything Claude or a script needs)
* ``profile.json``  - the dataset profile on its own
* ``forecast.csv``  - ``series, ds, forecast, lo_80, hi_80, lo_95, hi_95, model``
* ``backtest.csv``  - one row per (model, window, step): the audit trail behind every metric
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from forecast.backtest import FRAME_COLUMNS
from forecast.pipeline import FORECAST_COLUMNS, Outcome
from forecast.schema import RunResult

_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


def write_backtest_csv(frame: pd.DataFrame, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame[FRAME_COLUMNS].to_csv(out, index=False, date_format=_DATE_FORMAT)
    return out


def write_forecast_csv(frame: pd.DataFrame, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame[FORECAST_COLUMNS].to_csv(out, index=False, date_format=_DATE_FORMAT)
    return out


def write_artifacts(outcome: Outcome, directory: str | Path) -> RunResult:
    """Write every file of a successful run; returns the result with its artifact paths filled in."""
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    artifacts = outcome.result.artifacts.model_copy(update={"directory": str(out.resolve())})
    result = outcome.result.model_copy(update={"artifacts": artifacts})
    write_forecast_csv(outcome.forecast, out / artifacts.forecast_csv)
    write_backtest_csv(outcome.backtest, out / artifacts.backtest_csv)
    (out / artifacts.profile_json).write_text(result.profile.model_dump_json(indent=2) + "\n")
    (out / artifacts.result_json).write_text(result.model_dump_json(indent=2) + "\n")
    return result
