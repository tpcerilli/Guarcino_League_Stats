"""JSON cache of per-season derived stats, so re-runs don't re-hit the ESPN API."""
from __future__ import annotations

import json
from pathlib import Path

from .config import Config
from .espn_client import get_league
from .extract import extract_season
from .models import TeamSeasonStats

CACHE_DIR = Path("data/cache")


def _cache_path(year: int) -> Path:
    return CACHE_DIR / f"{year}.json"


def load_year(year: int) -> list[TeamSeasonStats] | None:
    path = _cache_path(year)
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return [TeamSeasonStats.from_dict(t) for t in data["teams"]]


def save_year(year: int, teams: list[TeamSeasonStats]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"teams": [t.to_dict() for t in teams]}
    _cache_path(year).write_text(json.dumps(payload, indent=2))


def build_all_seasons(
    config: Config, refresh: bool = False
) -> dict[int, list[TeamSeasonStats]]:
    """Loads every season from start_year..current_year, using the cache where possible.

    Past/completed seasons are fetched at most once and never touched again unless `refresh=True`
    ("don't re-upload stats from years ago"). The current (in-progress) season is always
    re-fetched live.
    """
    seasons: dict[int, list[TeamSeasonStats]] = {}
    for year in range(config.start_year, config.current_year + 1):
        is_current = year == config.current_year
        cached = None if (refresh or is_current) else load_year(year)

        if cached is not None:
            seasons[year] = cached
            continue

        league = get_league(config, year)
        teams = extract_season(league, year)
        seasons[year] = teams
        if not is_current:
            # Only cache completed/past seasons; the live season shouldn't get frozen in cache.
            save_year(year, teams)
    return seasons
