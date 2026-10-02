"""Pandas-based aggregation of per-season stats into all-time / current / head-to-head views."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .identity import _load_overrides, resolve_manager_key
from .models import TeamSeasonStats

SeasonsData = dict[int, list[TeamSeasonStats]]

STANDINGS_OVERRIDES_PATH = Path("config/standings_overrides.json")


def _load_standings_overrides() -> dict:
    if not STANDINGS_OVERRIDES_PATH.exists():
        return {}
    data = json.loads(STANDINGS_OVERRIDES_PATH.read_text())
    return data.get("final_standing_overrides", {})


def build_team_season_df(seasons: SeasonsData, manager_names: dict[str, str]) -> pd.DataFrame:
    rows = []
    overrides = _load_overrides()
    standing_overrides = _load_standings_overrides()
    for year, teams in seasons.items():
        year_overrides = standing_overrides.get(str(year), {})
        for team in teams:
            manager_key = resolve_manager_key(team, overrides)
            final_standing = year_overrides.get(str(team.team_id), team.final_standing)
            rows.append(
                {
                    "year": year,
                    "team_id": team.team_id,
                    "team_name": team.team_name,
                    "manager_key": manager_key,
                    "manager_name": manager_names.get(manager_key, team.team_name),
                    "wins": team.wins,
                    "losses": team.losses,
                    "ties": team.ties,
                    "points_for": team.points_for,
                    "points_against": team.points_against,
                    "standing": team.standing,
                    "final_standing": final_standing,
                    "made_playoffs": team.made_playoffs,
                    "acquisitions": team.acquisitions,
                    "drops": team.drops,
                    "trades": team.trades,
                }
            )
    return pd.DataFrame(rows)


def build_weekly_df(seasons: SeasonsData, team_season_df: pd.DataFrame) -> pd.DataFrame:
    manager_lookup = team_season_df.set_index(["year", "team_id"])["manager_key"].to_dict()
    name_lookup = team_season_df.set_index(["year", "team_id"])["manager_name"].to_dict()

    rows = []
    for year, teams in seasons.items():
        for team in teams:
            manager_key = manager_lookup.get((year, team.team_id))
            manager_name = name_lookup.get((year, team.team_id))
            for wk in team.weekly:
                opponent_key = manager_lookup.get((year, wk.opponent_team_id))
                opponent_name = name_lookup.get((year, wk.opponent_team_id))
                rows.append(
                    {
                        "year": year,
                        "week": wk.week,
                        "team_id": team.team_id,
                        "manager_key": manager_key,
                        "manager_name": manager_name,
                        "opponent_team_id": wk.opponent_team_id,
                        "opponent_key": opponent_key,
                        "opponent_name": opponent_name,
                        "points_for": wk.points_for,
                        "points_against": wk.points_against,
                        "result": wk.result,
                        "is_playoff": wk.is_playoff,
                    }
                )
    df = pd.DataFrame(rows)
    made_playoffs_lookup = team_season_df.set_index(["year", "team_id"])["made_playoffs"].to_dict()
    df["team_made_playoffs"] = df.apply(
        lambda r: made_playoffs_lookup.get((r["year"], r["team_id"]), False), axis=1
    )

    # Once a team loses a real-playoff-bracket game they're eliminated from the championship;
    # any later games that season (3rd/5th-place consolation, etc.) don't count toward playoff
    # stats. The losing game itself still counts — only weeks *after* it are excluded.
    df["playoff_counted"] = True
    playoff_mask = df["is_playoff"] & df["team_made_playoffs"]
    for (_year, _team_id), group in df[playoff_mask].groupby(["year", "team_id"]):
        losses = group.loc[group["result"] == "L", "week"]
        if not losses.empty:
            first_loss_week = losses.min()
            after_elimination = group[group["week"] > first_loss_week].index
            df.loc[after_elimination, "playoff_counted"] = False
    return df


def _longest_streaks(weekly_df: pd.DataFrame) -> pd.DataFrame:
    """Longest all-time win/loss streaks per manager, in chronological order across seasons
    (every game actually played counts; a tie breaks both streaks)."""
    rows = []
    for manager_key, group in weekly_df.sort_values(["year", "week"]).groupby("manager_key"):
        best_win = best_loss = cur_win = cur_loss = 0
        best_win_span = best_loss_span = None
        win_start = loss_start = None
        for row in group.itertuples():
            if row.result == "W":
                if cur_win == 0:
                    win_start = row.year
                cur_win += 1
                cur_loss = 0
                if cur_win > best_win:
                    best_win, best_win_span = cur_win, (win_start, row.year)
            elif row.result == "L":
                if cur_loss == 0:
                    loss_start = row.year
                cur_loss += 1
                cur_win = 0
                if cur_loss > best_loss:
                    best_loss, best_loss_span = cur_loss, (loss_start, row.year)
            else:  # tie breaks both streaks
                cur_win = cur_loss = 0
        rows.append(
            {
                "manager_key": manager_key,
                "longest_win_streak": best_win,
                "longest_win_streak_span": best_win_span,
                "longest_loss_streak": best_loss,
                "longest_loss_streak_span": best_loss_span,
            }
        )
    return pd.DataFrame(rows).set_index("manager_key")


def all_time_summary(team_season_df: pd.DataFrame, weekly_df: pd.DataFrame) -> pd.DataFrame:
    completed = team_season_df[team_season_df["final_standing"] > 0]
    g = team_season_df.groupby("manager_key")

    summary = g.agg(
        manager_name=("manager_name", "last"),
        seasons_played=("year", "nunique"),
        wins=("wins", "sum"),
        losses=("losses", "sum"),
        ties=("ties", "sum"),
        points_for=("points_for", "sum"),
        points_against=("points_against", "sum"),
        playoff_appearances=("made_playoffs", "sum"),
        acquisitions=("acquisitions", "sum"),
        drops=("drops", "sum"),
        trades=("trades", "sum"),
    )
    summary["win_pct"] = (summary["wins"] / (summary["wins"] + summary["losses"] + summary["ties"])).round(3)
    summary["point_diff"] = (summary["points_for"] - summary["points_against"]).round(2)

    champs = completed[completed["final_standing"] == 1].groupby("manager_key").size()
    runner_up = completed[completed["final_standing"] == 2].groupby("manager_key").size()
    third_place = completed[completed["final_standing"] == 3].groupby("manager_key").size()
    avg_final_standing = completed.groupby("manager_key")["final_standing"].mean().round(2)

    summary["championships"] = champs.reindex(summary.index, fill_value=0).astype(int)
    summary["runner_up_finishes"] = runner_up.reindex(summary.index, fill_value=0).astype(int)
    summary["third_place_finishes"] = third_place.reindex(summary.index, fill_value=0).astype(int)
    summary["avg_final_standing"] = avg_final_standing.reindex(summary.index)

    # Best/worst single season point total (completed seasons only — an in-progress season
    # would otherwise always look like a "worst" season on a partial point total).
    season_pf = completed.loc[completed.groupby("manager_key")["points_for"].idxmax()]
    worst_season_candidates = completed[completed["year"] != 2012]
    season_pf_min = worst_season_candidates.loc[worst_season_candidates.groupby("manager_key")["points_for"].idxmin()]
    summary["best_season_points"] = season_pf.set_index("manager_key")["points_for"]
    summary["best_season_points_year"] = season_pf.set_index("manager_key")["year"]
    summary["worst_season_points"] = season_pf_min.set_index("manager_key")["points_for"]
    summary["worst_season_points_year"] = season_pf_min.set_index("manager_key")["year"]

    # Best/worst single-game score
    best_game = weekly_df.loc[weekly_df.groupby("manager_key")["points_for"].idxmax()]
    worst_game_candidates = weekly_df[weekly_df["year"] != 2012]
    worst_game = worst_game_candidates.loc[worst_game_candidates.groupby("manager_key")["points_for"].idxmin()]
    summary["best_game_score"] = best_game.set_index("manager_key")["points_for"]
    summary["best_game_year"] = best_game.set_index("manager_key")["year"]
    summary["best_game_week"] = best_game.set_index("manager_key")["week"]
    summary["best_game_opponent"] = best_game.set_index("manager_key")["opponent_name"]
    summary["worst_game_score"] = worst_game.set_index("manager_key")["points_for"]
    summary["worst_game_year"] = worst_game.set_index("manager_key")["year"]
    summary["worst_game_week"] = worst_game.set_index("manager_key")["week"]

    # Playoff win/loss record: only count postseason games for teams that actually made the
    # real playoff bracket (see note in extract.py about the parallel consolation bracket), and
    # stop counting once a team is eliminated (games after their first playoff loss don't count).
    playoff_games = weekly_df[
        weekly_df["is_playoff"] & weekly_df["team_made_playoffs"] & weekly_df["playoff_counted"]
    ]
    playoff_wins = playoff_games[playoff_games["result"] == "W"].groupby("manager_key").size()
    playoff_losses = playoff_games[playoff_games["result"] == "L"].groupby("manager_key").size()
    summary["playoff_wins"] = playoff_wins.reindex(summary.index, fill_value=0).astype(int)
    summary["playoff_losses"] = playoff_losses.reindex(summary.index, fill_value=0).astype(int)
    playoff_game_count = (summary["playoff_wins"] + summary["playoff_losses"]).astype(float)
    playoff_game_count = playoff_game_count.replace(0, float("nan"))
    summary["playoff_win_pct"] = (summary["playoff_wins"] / playoff_game_count).round(3)

    games = summary["wins"] + summary["losses"] + summary["ties"]
    summary["avg_points_for"] = (summary["points_for"] / games).round(2)
    summary["avg_points_against"] = (summary["points_against"] / games).round(2)

    summary["total_moves"] = summary["acquisitions"] + summary["drops"] + summary["trades"]
    summary["acquisitions_per_season"] = (summary["acquisitions"] / summary["seasons_played"]).round(1)

    streaks = _longest_streaks(weekly_df)
    summary = summary.join(streaks)

    return summary.reset_index().sort_values("championships", ascending=False)


def current_season_snapshot(team_season_df: pd.DataFrame, weekly_df: pd.DataFrame, year: int) -> pd.DataFrame:
    season = team_season_df[team_season_df["year"] == year].copy()
    season["rank_key"] = season["final_standing"].where(season["final_standing"] > 0, season["standing"])
    season = season.sort_values("rank_key")
    cols = [
        "manager_name",
        "team_name",
        "wins",
        "losses",
        "ties",
        "points_for",
        "points_against",
        "standing",
    ]
    return season[cols].reset_index(drop=True)


def season_by_season(team_season_df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "year",
        "manager_name",
        "team_name",
        "wins",
        "losses",
        "ties",
        "points_for",
        "points_against",
        "final_standing",
        "made_playoffs",
    ]
    return team_season_df[cols].sort_values(["year", "final_standing"]).reset_index(drop=True)


def head_to_head(weekly_df: pd.DataFrame) -> pd.DataFrame:
    played = weekly_df[weekly_df["opponent_key"].notna() & (weekly_df["opponent_key"] != weekly_df["manager_key"])]
    grouped = played.groupby(["manager_name", "opponent_name", "result"]).size().unstack(fill_value=0)
    for col in ("W", "L", "T"):
        if col not in grouped.columns:
            grouped[col] = 0
    grouped = grouped.rename(columns={"W": "wins", "L": "losses", "T": "ties"})
    grouped["games"] = grouped["wins"] + grouped["losses"] + grouped["ties"]
    grouped["win_pct"] = (grouped["wins"] / grouped["games"]).round(3)
    return grouped.reset_index()


def _record_from_weekly(weekly_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregates W/L/T + points into one row per manager from a (pre-filtered) set of games."""
    g = weekly_df.groupby("manager_key")
    wins = weekly_df[weekly_df["result"] == "W"].groupby("manager_key").size()
    losses = weekly_df[weekly_df["result"] == "L"].groupby("manager_key").size()
    ties = weekly_df[weekly_df["result"] == "T"].groupby("manager_key").size()

    record = pd.DataFrame(
        {"games": g.size(), "points_for": g["points_for"].sum(), "points_against": g["points_against"].sum()}
    )
    record["wins"] = wins.reindex(record.index, fill_value=0).astype(int)
    record["losses"] = losses.reindex(record.index, fill_value=0).astype(int)
    record["ties"] = ties.reindex(record.index, fill_value=0).astype(int)
    record["win_pct"] = (record["wins"] / record["games"]).round(3)
    record["avg_points_for"] = (record["points_for"] / record["games"]).round(2)
    record["avg_points_against"] = (record["points_against"] / record["games"]).round(2)
    return record


def regular_season_summary(team_season_df: pd.DataFrame, weekly_df: pd.DataFrame) -> pd.DataFrame:
    """All-time record/points using only regular-season games (excludes all postseason weeks)."""
    record = _record_from_weekly(weekly_df[~weekly_df["is_playoff"]])
    names = team_season_df.drop_duplicates("manager_key").set_index("manager_key")["manager_name"]
    record["manager_name"] = names.reindex(record.index)
    return record.reset_index().sort_values("win_pct", ascending=False)


def _playoff_bye_weeks(team_season_df: pd.DataFrame, weekly_df: pd.DataFrame) -> pd.Series:
    """Counts first-round playoff byes (a scheduled playoff week with no game for that team,
    while the league played other playoff games that same week — i.e. a top seed's round-1 bye).
    """
    playoff_rows = weekly_df[weekly_df["is_playoff"]]
    league_weeks_by_year = playoff_rows.groupby("year")["week"].apply(set)
    team_weeks = playoff_rows.groupby(["year", "team_id"])["week"].apply(set)

    byes: dict[str, int] = {}
    made_playoffs = team_season_df[team_season_df["made_playoffs"]]
    for row in made_playoffs.itertuples():
        played = team_weeks.get((row.year, row.team_id), set())
        if not played:
            continue  # e.g. current season: made the bracket but hasn't played a playoff game yet
        league_weeks = league_weeks_by_year.get(row.year, set())
        n_byes = len([w for w in league_weeks if w < max(played) and w not in played])
        byes[row.manager_key] = byes.get(row.manager_key, 0) + n_byes
    return pd.Series(byes, name="bye_weeks")


def playoff_summary(team_season_df: pd.DataFrame, weekly_df: pd.DataFrame) -> pd.DataFrame:
    """All-time record/points using only real-playoff-bracket games (excludes the consolation
    bracket and regular season — see extract.py note on made_playoffs vs is_playoff), and
    stops counting a team's games once they've been eliminated (first playoff loss)."""
    playoff_games = weekly_df[
        weekly_df["is_playoff"] & weekly_df["team_made_playoffs"] & weekly_df["playoff_counted"]
    ]
    record = _record_from_weekly(playoff_games)
    names = team_season_df.drop_duplicates("manager_key").set_index("manager_key")["manager_name"]
    record["manager_name"] = names.reindex(record.index)
    appearances = team_season_df[team_season_df["made_playoffs"]].groupby("manager_key").size()
    record["appearances"] = appearances.reindex(record.index, fill_value=0).astype(int)
    bye_weeks = _playoff_bye_weeks(team_season_df, weekly_df)
    record["bye_weeks"] = bye_weeks.reindex(record.index, fill_value=0).astype(int)
    championships = team_season_df[team_season_df["final_standing"] == 1].groupby("manager_key").size()
    runner_up = team_season_df[team_season_df["final_standing"] == 2].groupby("manager_key").size()
    record["championships"] = championships.reindex(record.index, fill_value=0).astype(int)
    record["runner_up_finishes"] = runner_up.reindex(record.index, fill_value=0).astype(int)
    return record.reset_index().sort_values("win_pct", ascending=False)
