"""Writes aggregate tables to CSV under output/csv/."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

OUTPUT_DIR = Path("output/csv")


def write_csv_reports(
    all_time: pd.DataFrame,
    regular_season: pd.DataFrame,
    playoffs: pd.DataFrame,
    season_by_season: pd.DataFrame,
    head_to_head: pd.DataFrame,
    current_season: pd.DataFrame,
) -> list[Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    files = {
        "all_time_summary.csv": all_time,
        "regular_season_summary.csv": regular_season,
        "playoff_summary.csv": playoffs,
        "season_by_season.csv": season_by_season,
        "head_to_head.csv": head_to_head,
        "current_season_standings.csv": current_season,
    }
    written = []
    for name, df in files.items():
        path = OUTPUT_DIR / name
        df.to_csv(path, index=False)
        written.append(path)
    return written
