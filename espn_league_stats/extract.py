"""Converts a fetched espn_api League object into serializable stat records."""
from __future__ import annotations

from espn_api.football import League

from .models import TeamSeasonStats, WeeklyResult


def _opponent_id_and_score(opponent, week_index: int, own_team_id: int) -> tuple[int, float]:
    """Resolve opponent team id + their score for a given week; handles byes."""
    if hasattr(opponent, "team_id"):
        opponent_id = opponent.team_id
        opponent_scores = getattr(opponent, "scores", [])
        opponent_score = opponent_scores[week_index] if week_index < len(opponent_scores) else 0.0
    else:
        # legacy shape: opponent is a raw team id, or self on a bye
        opponent_id = int(opponent) if opponent is not None else own_team_id
        opponent_score = 0.0
    return opponent_id, opponent_score


def extract_team_season(team, year: int, reg_season_weeks: int, playoff_team_count: int) -> TeamSeasonStats:
    weekly: list[WeeklyResult] = []
    for i, (score, outcome) in enumerate(zip(team.scores, team.outcomes)):
        if outcome == "U":
            continue  # week not yet played
        week = i + 1
        opponent = team.schedule[i] if i < len(team.schedule) else None
        opponent_id, opponent_score = _opponent_id_and_score(opponent, i, team.team_id)
        weekly.append(
            WeeklyResult(
                week=week,
                opponent_team_id=opponent_id,
                points_for=round(float(score), 2),
                points_against=round(float(opponent_score), 2),
                result=outcome,
                is_playoff=week > reg_season_weeks,
            )
        )

    owners = getattr(team, "owners", []) or []
    # Weeks after reg_season_weeks include both the real playoff bracket and a parallel
    # consolation bracket; only a top-`playoff_team_count` seed actually made the real playoffs.
    made_playoffs = bool(playoff_team_count) and 0 < team.standing <= playoff_team_count
    return TeamSeasonStats(
        year=year,
        team_id=team.team_id,
        team_name=team.team_name,
        owner_ids=[o.get("id", "") for o in owners],
        owner_names=[o.get("displayName", "") for o in owners],
        wins=team.wins,
        losses=team.losses,
        ties=team.ties,
        points_for=round(float(team.points_for), 2),
        points_against=round(float(team.points_against), 2),
        standing=team.standing,
        final_standing=team.final_standing or 0,
        made_playoffs=made_playoffs,
        streak_length=getattr(team, "streak_length", 0),
        streak_type=getattr(team, "streak_type", ""),
        acquisitions=getattr(team, "acquisitions", 0),
        drops=getattr(team, "drops", 0),
        trades=getattr(team, "trades", 0),
        reg_season_weeks=reg_season_weeks,
        playoff_team_count=playoff_team_count,
        weekly=weekly,
    )


def extract_season(league: League, year: int) -> list[TeamSeasonStats]:
    reg_season_weeks = league.settings.reg_season_count
    playoff_team_count = league.settings.playoff_team_count
    return [
        extract_team_season(team, year, reg_season_weeks, playoff_team_count)
        for team in league.teams
    ]
