"""Loads and validates league configuration from the environment."""
from __future__ import annotations

import datetime
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    league_id: int
    espn_s2: str
    swid: str
    start_year: int
    current_year: int


def load_config() -> Config:
    league_id = os.environ.get("LEAGUE_ID")
    espn_s2 = os.environ.get("ESPN_S2")
    swid = os.environ.get("SWID")
    start_year = os.environ.get("START_YEAR", "2012")

    missing = [
        name
        for name, value in (("LEAGUE_ID", league_id), ("ESPN_S2", espn_s2), ("SWID", swid))
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"Missing required .env values: {', '.join(missing)}. "
            "Copy .env.example to .env and fill in your league's values."
        )

    # NFL season year rolls over in March; before that we're still reporting on the prior season.
    today = datetime.date.today()
    current_year = today.year if today.month >= 3 else today.year - 1

    return Config(
        league_id=int(league_id),
        espn_s2=espn_s2,
        swid=swid,
        start_year=int(start_year),
        current_year=current_year,
    )
