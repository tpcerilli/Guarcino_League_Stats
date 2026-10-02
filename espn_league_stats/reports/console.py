"""Console output via rich tables."""
from __future__ import annotations

import sys

import pandas as pd
from rich.console import Console
from rich.table import Table

# Team/manager names can contain arbitrary unicode (e.g. "₿"); on legacy Windows console
# codepages that can't encode it, fall back to replacing the character instead of crashing.
try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass

console = Console()


def print_all_time_leaderboard(df: pd.DataFrame) -> None:
    table = Table(title="Combined Leaderboard")
    for col in ("Manager", "W", "L", "T", "Win%", "PF", "PA", "Titles", "2nd", "Playoffs"):
        table.add_column(col)
    for _, row in df.iterrows():
        table.add_row(
            row["manager_name"],
            str(row["wins"]),
            str(row["losses"]),
            str(row["ties"]),
            f"{row['win_pct'] * 100:.1f}%",
            f"{row['points_for']:.1f}",
            f"{row['points_against']:.1f}",
            str(row["championships"]),
            str(row["runner_up_finishes"]),
            str(row["playoff_appearances"]),
        )
    console.print(table)


def print_current_season(df: pd.DataFrame, year: int) -> None:
    table = Table(title=f"Current Season Standings ({year})")
    for col in ("Rank", "Manager", "Team", "W", "L", "T", "PF", "PA"):
        table.add_column(col)
    for i, row in enumerate(df.itertuples(), start=1):
        table.add_row(
            str(i),
            row.manager_name,
            row.team_name,
            str(row.wins),
            str(row.losses),
            str(row.ties),
            f"{row.points_for:.1f}",
            f"{row.points_against:.1f}",
        )
    console.print(table)


def _fmt_season(points, year) -> str:
    if pd.isna(points) or pd.isna(year):
        return "n/a (no completed season)"
    return f"{points:.1f} ({int(year)})"


def print_records(df: pd.DataFrame) -> None:
    table = Table(title="Combined Records")
    table.add_column("Manager")
    table.add_column("Best Season PF (yr)")
    table.add_column("Worst Season PF (yr)")
    table.add_column("Best Game (yr/wk vs)")
    table.add_column("Worst Game (yr/wk)")
    for _, row in df.iterrows():
        table.add_row(
            row["manager_name"],
            _fmt_season(row["best_season_points"], row["best_season_points_year"]),
            _fmt_season(row["worst_season_points"], row["worst_season_points_year"]),
            f"{row['best_game_score']:.1f} ({int(row['best_game_year'])} wk{int(row['best_game_week'])} vs {row['best_game_opponent']})",
            f"{row['worst_game_score']:.1f} ({int(row['worst_game_year'])} wk{int(row['worst_game_week'])})",
        )
    console.print(table)


def print_season_by_season(df: pd.DataFrame) -> None:
    ordered = df.sort_values(
        ["year", "final_standing"], ascending=[False, True]
    )
    for year, group in ordered.groupby("year", sort=False):
        table = Table(title=f"Results By Season ({year})")
        for col in ("Manager", "Team", "W", "L", "T", "PF", "PA", "Final Standing", "Playoffs"):
            table.add_column(col)
        for row in group.itertuples():
            table.add_row(
                row.manager_name,
                row.team_name,
                str(row.wins),
                str(row.losses),
                str(row.ties),
                f"{row.points_for:.1f}",
                f"{row.points_against:.1f}",
                str(row.final_standing) if row.final_standing else "-",
                "Yes" if row.made_playoffs else "No",
            )
        console.print(table)


def print_regular_vs_playoff(regular_df: pd.DataFrame, playoff_df: pd.DataFrame) -> None:
    table = Table(title="Regular Season vs Playoffs (all-time)")
    for col in (
        "Manager",
        "Reg W-L-T",
        "Reg Win%",
        "Reg PF",
        "Reg PA",
        "Reg Avg PF",
        "Reg Avg PA",
        "Playoff Apps",
        "Playoff W-L-T",
        "Playoff Win%",
        "Playoff PF",
        "Playoff PA",
    ):
        table.add_column(col)
    playoff_by_key = playoff_df.set_index("manager_key")
    for row in regular_df.itertuples():
        p = playoff_by_key.loc[row.manager_key] if row.manager_key in playoff_by_key.index else None
        table.add_row(
            row.manager_name,
            f"{row.wins}-{row.losses}-{row.ties}",
            f"{row.win_pct * 100:.1f}%",
            f"{row.points_for:.1f}",
            f"{row.points_against:.1f}",
            f"{row.avg_points_for:.1f}",
            f"{row.avg_points_against:.1f}",
            str(int(p.appearances)) if p is not None else "0",
            f"{int(p.wins)}-{int(p.losses)}-{int(p.ties)}" if p is not None else "0-0-0",
            f"{p.win_pct * 100:.1f}%" if p is not None and pd.notna(p.win_pct) else "n/a",
            f"{p.points_for:.1f}" if p is not None else "0.0",
            f"{p.points_against:.1f}" if p is not None else "0.0",
        )
    console.print(table)
