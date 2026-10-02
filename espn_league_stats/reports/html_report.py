"""Builds the static HTML dashboard: summary tables + Chart.js charts, no build step."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

OUTPUT_DIR = Path("output/html")
TEMPLATE_DIR = Path(__file__).parent / "templates"


def _points_trend(season_by_season: pd.DataFrame) -> dict:
    years = sorted(season_by_season["year"].unique().tolist())
    datasets = []
    for manager, group in season_by_season.groupby("manager_name"):
        by_year = group.set_index("year")["points_for"].to_dict()
        datasets.append({"label": manager, "data": [by_year.get(y) for y in years]})
    return {"labels": years, "datasets": datasets}


def _standings_over_time(season_by_season: pd.DataFrame) -> dict:
    years = sorted(season_by_season["year"].unique().tolist())
    datasets = []
    for manager, group in season_by_season.groupby("manager_name"):
        by_year = group.set_index("year")["final_standing"].to_dict()
        datasets.append(
            {"label": manager, "data": [by_year.get(y) or None for y in years]}
        )
    return {"labels": years, "datasets": datasets}


def _bar(all_time: pd.DataFrame, value_col: str, scale: float = 1) -> dict:
    ordered = all_time.sort_values(value_col, ascending=False)
    values = (ordered[value_col] * scale).tolist()
    return {"labels": ordered["manager_name"].tolist(), "values": values}


def _pf_pa(all_time: pd.DataFrame) -> dict:
    ordered = all_time.sort_values("avg_points_for", ascending=False)
    return {
        "labels": ordered["manager_name"].tolist(),
        "points_for": ordered["avg_points_for"].tolist(),
        "points_against": ordered["avg_points_against"].tolist(),
    }


def _playoffs(all_time: pd.DataFrame) -> dict:
    ordered = all_time.sort_values("playoff_appearances", ascending=False)
    return {
        "labels": ordered["manager_name"].tolist(),
        "appearances": ordered["playoff_appearances"].tolist(),
        # displayed as a percentage (0-100), unlike the 0-1 fraction used for the h2h heatmap alpha
        "win_pct": (ordered["playoff_win_pct"].fillna(0) * 100).tolist(),
    }


def _head_to_head_cells(head_to_head: pd.DataFrame) -> dict:
    managers = sorted(set(head_to_head["manager_name"]) | set(head_to_head["opponent_name"]))
    cells = {m: {o: None for o in managers} for m in managers}
    for row in head_to_head.itertuples():
        cells[row.manager_name][row.opponent_name] = {
            "wins": row.wins,
            "losses": row.losses,
            "ties": row.ties,
            "win_pct": row.win_pct,
        }
    return {"managers": managers, "cells": cells}


def _season_groups(season_by_season: pd.DataFrame) -> list[dict]:
    ordered = season_by_season.sort_values(["year", "final_standing"], ascending=[False, True])
    return [
        {"year": int(year), "rows": group.to_dict(orient="records")}
        for year, group in ordered.groupby("year", sort=False)
    ]


def write_html_report(
    all_time: pd.DataFrame,
    regular_season: pd.DataFrame,
    playoffs: pd.DataFrame,
    season_by_season: pd.DataFrame,
    head_to_head: pd.DataFrame,
    current_season: pd.DataFrame,
    current_year: int,
) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=select_autoescape(["html"])
    )
    template = env.get_template("index.html.j2")

    charts = {
        "points_trend": _points_trend(season_by_season),
        "championships": _bar(all_time, "championships"),
        "win_pct": _bar(all_time, "win_pct", scale=100),
        "pf_pa": _pf_pa(all_time),
        "standings_over_time": _standings_over_time(season_by_season),
        "playoffs": _playoffs(all_time),
    }
    h2h = _head_to_head_cells(head_to_head)

    html = template.render(
        current_year=current_year,
        all_time=all_time.to_dict(orient="records"),
        regular_season=regular_season.to_dict(orient="records"),
        playoffs=playoffs.to_dict(orient="records"),
        current_season=current_season.to_dict(orient="records"),
        season_groups=_season_groups(season_by_season),
        charts_json=json.dumps(charts),
        h2h_managers=h2h["managers"],
        h2h_cells=h2h["cells"],
    )
    out_path = OUTPUT_DIR / "index.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
