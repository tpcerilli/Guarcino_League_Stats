# Guarcino League Stats

ESPN Fantasy Football league history + current-season stats: console tables, CSV exports, and
an HTML dashboard with charts.

Go to https://tpcerilli.github.io/Guarcino_League_Stats/ to view current statistics.

## Setup

1. `python -m venv .venv`
2. `.\.venv\Scripts\pip install -r requirements.txt` (Windows) or `source .venv/bin/activate && pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in:
   - `LEAGUE_ID` — from your league URL (`?leagueId=...`)
   - `ESPN_S2` / `SWID` — cookies from a logged-in browser session (DevTools → Application →
     Cookies → fantasy.espn.com). These expire periodically; if runs start failing with 401s,
     grab fresh values.
   - `START_YEAR` — first season to include.

## Usage

```
python -m espn_league_stats.main
```

Outputs:
- Console tables (all-time leaderboard, current standings, records)
- `output/csv/*.csv`
- `output/html/Guarcino_Stats.html` (open in any browser)

Flags: `--refresh` (force re-fetch everything), `--start-year YYYY`, `--no-csv`, `--no-html`.

### How caching works

Past/completed seasons are fetched once and cached in `data/cache/` — they're never re-fetched
on later runs (use `--refresh` to force it). The current season is always re-fetched live, and
its per-player point data (used for draft pick value) is updated incrementally — only weeks
played since your last run are fetched.

### Manager identity

Stats are grouped by ESPN owner account across years (not team name, which can change). If a
team-season can't be mapped to an owner, the run prints a warning — add an override to
`config/manager_map.json` to fix it.
