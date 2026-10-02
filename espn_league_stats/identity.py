"""Resolves a stable "manager" identity for a team-season across years.

ESPN team names/branding can change year to year, but each ESPN login has a stable owner
member id. We group by owner id (first owner listed, i.e. primary owner) and use their most
recent displayName as the canonical label, with an optional manual JSON override file for
edge cases (co-owned teams, seasons with missing owner data).
"""
from __future__ import annotations

import json
from pathlib import Path

from .models import TeamSeasonStats

MANAGER_MAP_PATH = Path("config/manager_map.json")


def _load_overrides() -> dict:
    if not MANAGER_MAP_PATH.exists():
        return {"owner_names": {}, "team_overrides": {}}
    return json.loads(MANAGER_MAP_PATH.read_text())


def resolve_manager_key(team: TeamSeasonStats, overrides: dict) -> str | None:
    """Returns a stable manager key for this team-season, or None if unmappable."""
    team_override_key = f"{team.year}:{team.team_id}"
    if team_override_key in overrides.get("team_overrides", {}):
        return overrides["team_overrides"][team_override_key]
    if team.owner_ids:
        return team.owner_ids[0]
    return None


def build_manager_registry(
    all_seasons: dict[int, list[TeamSeasonStats]],
) -> tuple[dict[str, str], list[str]]:
    """Returns (manager_key -> display_name) and a list of warning strings for unmapped teams."""
    overrides = _load_overrides()
    owner_name_overrides = overrides.get("owner_names", {})

    display_names: dict[str, str] = {}
    warnings: list[str] = []

    for year in sorted(all_seasons):
        teams = all_seasons[year]
        for team in teams:
            key = resolve_manager_key(team, overrides)
            if key is None:
                warnings.append(
                    f"{year}: team_id={team.team_id} ({team.team_name!r}) has no owner data "
                    "and no manager_map.json override — add one to include it in manager stats."
                )
                continue
            # Later seasons' displayName wins so the name reflects the manager's current handle.
            if key in owner_name_overrides:
                display_names[key] = owner_name_overrides[key]
            elif team.owner_names and team.owner_names[0]:
                display_names[key] = team.owner_names[0]
            elif key not in display_names:
                display_names[key] = team.team_name

    return display_names, warnings
