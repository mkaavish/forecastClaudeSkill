"""Writers for result files. Phase 4 contains only the backtest table; later phases add the rest."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from forecast.backtest import FRAME_COLUMNS


def write_backtest_csv(frame: pd.DataFrame, path: str | Path) -> Path:
    """One row per (model, window, step): the audit trail behind every metric."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame[FRAME_COLUMNS].to_csv(out, index=False, date_format="%Y-%m-%dT%H:%M:%S")
    return out
