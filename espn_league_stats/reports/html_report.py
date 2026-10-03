"""Builds the static HTML dashboard: summary tables + Chart.js charts, no build step."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape

OUTPUT_DIR = Path("output/html")
TEMPLATE_DIR = Path(__file__).parent / "templates"
LOGO_CACHE_DIR = OUTPUT_DIR / "assets" / "logos"
CREST_PATH = TEMPLATE_DIR / "assets" / "bakery_logo.jpg"
# Custom-uploaded team logos are served from this auth-gated ESPN endpoint (unlike the public
# logo-pack images on g.espncdn.com) and 403 for visitors without ESPN login cookies.
GATED_LOGO_PREFIX = "https://mystique-api.fantasy.espn.com/"


def _crest_data_uri() -> str:
    """Embeds the header crest image inline so the HTML stays a single, self-contained file
    (e.g. still works when opened as a saved email attachment, per the noscript fallback notice)."""
    if not CREST_PATH.exists():
        return ""
    import base64

    encoded = base64.b64encode(CREST_PATH.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _localize_gated_logos(dfs: list[pd.DataFrame], espn_s2: str, swid: str) -> dict[str, str]:
    """Downloads any auth-gated custom team logos found in `dfs` to a local assets folder
    (using our own ESPN cookies) and returns a mapping of original url -> local relative path."""
    urls: set[str] = set()
    for df in dfs:
        if "logo_url" in df.columns:
            urls.update(u for u in df["logo_url"].dropna().unique() if u.startswith(GATED_LOGO_PREFIX))
    if not urls:
        return {}

    LOGO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, str] = {}
    for url in urls:
        digest = hashlib.sha1(url.encode()).hexdigest()[:16]
        local_path = LOGO_CACHE_DIR / f"{digest}.png"
        if not local_path.exists():
            try:
                resp = requests.get(url, cookies={"espn_s2": espn_s2, "SWID": swid}, timeout=10)
                resp.raise_for_status()
                local_path.write_bytes(resp.content)
            except requests.RequestException:
                continue
        mapping[url] = f"assets/logos/{digest}.png"
    return mapping


def _apply_logo_mapping(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    if not mapping or "logo_url" not in df.columns:
        return df
    df = df.copy()
    df["logo_url"] = df["logo_url"].map(lambda u: mapping.get(u, u))
    return df


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


def _cumulative_over_time(season_by_season: pd.DataFrame, value_col: str) -> dict:
    """Running career total of `value_col` (e.g. points_for, wins) by year, per manager."""
    years = sorted(season_by_season["year"].unique().tolist())
    datasets = []
    for manager, group in season_by_season.groupby("manager_name"):
        by_year = group.set_index("year")[value_col].to_dict()
        running_total = 0
        data = []
        for y in years:
            running_total += by_year.get(y, 0)
            data.append(running_total)
        datasets.append({"label": manager, "data": data})
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


def _diverging_color(win_pct: float) -> str:
    """Green for winning, white for .500, red for losing — scaled by how far from .500.

    A small handful of matchups sit at exactly 0.0/1.0 (e.g. a 1-0 all-time record), which would
    otherwise saturate the color scale and make every more-typical record look washed-out/white
    by comparison. A sqrt curve pulls moderate records (.6, .7, etc.) much further from white
    while still capping at full saturation only for true 0/1 records.
    Endpoints are pastel (not fully saturated) so dark cell text stays readable throughout.
    """
    red, green, blue = 255, 255, 255
    if win_pct > 0.5:
        t = ((win_pct - 0.5) / 0.5) ** 0.5  # 0..1 toward pastel green
        red = round(255 - (255 - 129) * t)
        green = round(255 - (255 - 199) * t)
        blue = round(255 - (255 - 132) * t)
    elif win_pct < 0.5:
        t = ((0.5 - win_pct) / 0.5) ** 0.5  # 0..1 toward pastel red
        red = round(255 - (255 - 239) * t)
        green = round(255 - (255 - 154) * t)
        blue = round(255 - (255 - 154) * t)
    return f"rgb({red},{green},{blue})"


def _head_to_head_cells(head_to_head: pd.DataFrame) -> dict:
    managers = sorted(set(head_to_head["manager_name"]) | set(head_to_head["opponent_name"]))
    cells = {m: {o: None for o in managers} for m in managers}
    for row in head_to_head.itertuples():
        cells[row.manager_name][row.opponent_name] = {
            "wins": row.wins,
            "losses": row.losses,
            "ties": row.ties,
            "win_pct": row.win_pct,
            "color": _diverging_color(row.win_pct),
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
    current_season_activity: pd.DataFrame,
    current_year: int,
    espn_s2: str,
    swid: str,
    general: dict,
    champ_years: pd.DataFrame,
) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logo_mapping = _localize_gated_logos(
        [current_season, current_season_activity, season_by_season], espn_s2, swid
    )
    current_season = _apply_logo_mapping(current_season, logo_mapping)
    current_season_activity = _apply_logo_mapping(current_season_activity, logo_mapping)
    season_by_season = _apply_logo_mapping(season_by_season, logo_mapping)
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
        "points_cumulative": _cumulative_over_time(season_by_season, "points_for"),
        "wins_cumulative": _cumulative_over_time(season_by_season, "wins"),
    }
    h2h = _head_to_head_cells(head_to_head)

    html = template.render(
        current_year=current_year,
        crest_data_uri=_crest_data_uri(),
        all_time=all_time.to_dict(orient="records"),
        regular_season=regular_season.to_dict(orient="records"),
        playoffs=playoffs.to_dict(orient="records"),
        current_season=current_season.to_dict(orient="records"),
        current_season_activity=current_season_activity.to_dict(orient="records"),
        season_groups=_season_groups(season_by_season),
        rank_titles=general["rank_titles"].to_dict(orient="records"),
        fun_facts=general["fun_facts"],
        champ_years=champ_years.to_dict(orient="records"),
        charts_json=json.dumps(charts),
        h2h_managers=h2h["managers"],
        h2h_cells=h2h["cells"],
    )
    out_path = OUTPUT_DIR / "Guarcino_Stats.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
