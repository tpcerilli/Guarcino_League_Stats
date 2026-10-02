"""Thin wrapper around espn_api.football.League with clearer auth error handling."""
from __future__ import annotations

from espn_api.football import League

from .config import Config


class EspnAuthError(RuntimeError):
    """Raised when ESPN rejects the configured espn_s2/SWID credentials."""


def get_league(config: Config, year: int) -> League:
    try:
        return League(
            league_id=config.league_id,
            year=year,
            espn_s2=config.espn_s2,
            swid=config.swid,
        )
    except Exception as exc:  # espn_api raises plain Exception/ConnectionError on HTTP errors
        message = str(exc)
        if "401" in message or "403" in message or "ESPN" in message:
            raise EspnAuthError(
                f"ESPN rejected the request for year {year} (likely expired/invalid "
                "espn_s2/SWID cookies). Refresh them from your browser and update .env."
            ) from exc
        raise
