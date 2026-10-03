"""CLI entry point: fetch/cache -> identity -> aggregate -> console/csv/html reports."""
from __future__ import annotations

import argparse

from .aggregate import (
    all_time_summary,
    build_team_season_df,
    build_weekly_df,
    championship_years,
    current_season_misc,
    current_season_snapshot,
    general_stats,
    head_to_head,
    playoff_summary,
    regular_season_finish_counts,
    regular_season_summary,
    season_by_season,
)
from .cache import build_all_seasons
from .config import load_config
from .identity import build_manager_registry
from .reports.console import (
    print_activity,
    print_all_time_leaderboard,
    print_current_season,
    print_records,
    print_regular_vs_playoff,
    print_season_by_season,
)
from .reports.csv_report import write_csv_reports
from .reports.html_report import write_html_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ESPN Fantasy Football league stats")
    parser.add_argument(
        "--refresh", action="store_true", help="Force re-fetch every season instead of using the cache"
    )
    parser.add_argument("--start-year", type=int, default=None, help="Override the league's start year")
    parser.add_argument("--no-csv", action="store_true", help="Skip writing CSV reports")
    parser.add_argument("--no-html", action="store_true", help="Skip writing the HTML dashboard")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config()
    if args.start_year:
        config = config.__class__(**{**config.__dict__, "start_year": args.start_year})

    print(f"Fetching seasons {config.start_year}-{config.current_year} for league {config.league_id}...")
    seasons = build_all_seasons(config, refresh=args.refresh)
    total_team_seasons = sum(len(teams) for teams in seasons.values())
    print(f"Loaded {len(seasons)} seasons, {total_team_seasons} team-seasons.")

    manager_names, warnings = build_manager_registry(seasons)
    if warnings:
        print(f"\n{len(warnings)} team-season(s) could not be mapped to a manager:")
        for w in warnings:
            print(f"  - {w}")
        print("Add entries to config/manager_map.json to resolve these.\n")

    team_season_df = build_team_season_df(seasons, manager_names)
    weekly_df = build_weekly_df(seasons, team_season_df)

    all_time = all_time_summary(team_season_df, weekly_df)
    regular_season = regular_season_summary(team_season_df, weekly_df, config.current_year)
    playoffs = playoff_summary(team_season_df, weekly_df)
    current_season = current_season_snapshot(team_season_df, weekly_df, config.current_year)
    current_season_activity = current_season_misc(team_season_df, weekly_df, config.current_year)
    season_table = season_by_season(team_season_df)
    h2h = head_to_head(weekly_df)
    general = general_stats(team_season_df)
    champ_years = championship_years(team_season_df)
    finish_counts = regular_season_finish_counts(team_season_df, config.current_year)

    print_all_time_leaderboard(all_time)
    print_current_season(current_season, config.current_year)
    print_records(all_time)
    print_regular_vs_playoff(regular_season, playoffs)
    print_activity(all_time)
    print_season_by_season(season_table)

    if not args.no_csv:
        paths = write_csv_reports(
            all_time, regular_season, playoffs, season_table, h2h, current_season, current_season_activity
        )
        print(f"\nWrote {len(paths)} CSV files to output/csv/")

    if not args.no_html:
        html_path = write_html_report(
            all_time,
            regular_season,
            playoffs,
            season_table,
            h2h,
            current_season,
            current_season_activity,
            config.current_year,
            config.espn_s2,
            config.swid,
            general,
            champ_years,
            finish_counts,
        )
        print(f"Wrote HTML dashboard to {html_path}")


if __name__ == "__main__":
    main()
