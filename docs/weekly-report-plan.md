# Plan: Weekly Report tab (newspaper style)

Last week's results + next week's matchups, written up as a newspaper-style recap page.

## Decisions
- **Format**: newspaper-style — a generated headline + narrative recap paragraph per matchup
  (not scoreboard cards, not a plain table).
- **Recap depth**: richer, stat-driven blurbs — each recap references the winner's/loser's
  season record, current win/loss streak, and all-time head-to-head series record between the
  two managers, not just the final score.
- **Layout scope**: recaps PLUS a compact "League Standings" sidebar box (through the most
  recent week), and a lighter-weight "This Week" preview section for the upcoming matchups.
- **No playoff-round labeling** — just "Week N" (no "Semifinal"/"Consolation" etc.).
- **Offseason/preseason**: friendly placeholder text when a section has no data yet (not
  silently hidden) — e.g. "Season hasn't started yet" / "Season complete — see you next year!".
- All recap text is deterministically assembled from real stats in Python (string-formatting
  rules based on margin/streak/h2h data, same pattern as the existing `fun_facts` list in
  `general_stats()`) — **not** free-form/LLM-generated text.

## Considered option: manual paste into a free web LLM
Instead of (or in addition to) the deterministic templated prose, the recap *input facts* (score,
margin, record, streak, head-to-head) could be printed each week — console output or a small
`data/weekly_recap_input.txt` — in a simple format ready to paste into a free web LLM chat (e.g.
ChatGPT/Claude/Gemini) with a "write newspaper-style recap paragraphs for these matchups" prompt.
The generated prose would then be pasted back into a file (e.g. `data/weekly_recap_text.json`,
keyed by year/week/matchup) that the aggregator reads if present, falling back to the deterministic
templated version when no manual recap exists yet for that week.
- **Pros**: free, no API key/dependency/network call, much more natural and varied prose than
  templated strings.
- **Cons**: not automated — requires a manual copy/paste step every week before regenerating the
  dashboard; needs a defined file format + fallback logic; output isn't guaranteed numerically
  accurate without double-checking against the source facts before pasting back in.
- **Status**: not adopted for the initial build — the plan proceeds with the deterministic
  templated approach below, but this remains a viable future enhancement if more natural prose is
  wanted later.

## Root problem
`weekly_df` only contains COMPLETED weeks (`extract.py` skips `outcome == "U"`). There is no
upcoming-matchup data anywhere yet, and no `current_week` concept — just `current_year`.
`team.schedule[i]` already holds the opponent for not-yet-played weeks too (the full schedule is
set before any scores exist), so upcoming matchups ARE obtainable from the live League object —
they're just currently discarded during extraction.

## Steps

### Phase A: Capture upcoming-matchup data (backend)
1. `espn_league_stats/models.py` — add `upcoming_week: int | None = None` and
   `upcoming_opponent_team_id: int | None = None` to `TeamSeasonStats` (defaults keep old cached
   JSON loadable via `from_dict`).
2. `espn_league_stats/extract.py` — in `extract_team_season`, while scanning `team.scores`/
   `team.outcomes`, capture the FIRST `outcome == "U"` week's `(week, opponent_id)` using the
   existing `_opponent_id_and_score` helper, and set it on the returned `TeamSeasonStats`. Past/
   completed seasons naturally have no "U" weeks so both fields stay `None`.
3. `espn_league_stats/aggregate.py`, `build_team_season_df` (*depends on 1-2*) — add
   `upcoming_week`/`upcoming_opponent_team_id` columns to the row dict (pull via `getattr(team,
   "upcoming_week", None)` for safety against stale cache objects from before this change).

### Phase B: Aggregate last-week + upcoming-week matchups, plus newspaper recap text
4. `espn_league_stats/aggregate.py` — new function `weekly_report(team_season_df, weekly_df,
   current_year) -> dict` (*depends on Phase A*):
   - `current_weekly = weekly_df[weekly_df.year == current_year]`; `last_week_num =
     current_weekly.week.max()` if non-empty else `None`.
   - **Last week section**: filter to `week == last_week_num`; dedupe symmetric rows (weekly_df
     has one row per team per matchup, so each pairing appears twice) by tracking seen
     `frozenset({team_id, opponent_team_id})`. For each matchup, build a recap dict:
     - `winner`/`loser` manager_name + team_name/logo_url + scores (margin = abs diff).
     - `margin_word`: formulaic descriptor from margin thresholds (e.g. >30 "blowout", <5
       "nailbiter"/"squeaker", else neutral) — used to vary the headline phrasing.
     - `winner_record`/`loser_record`: `f"{wins}-{losses}-{ties}"` pulled straight from
       `team_season_df` (wins/losses/ties are already season-to-date as of the latest fetch).
     - `winner_streak`: from `team_season_df`'s existing `streak_length`/`streak_type` columns
       (e.g. "W3"/"L2").
     - `h2h_record`: look up this manager pair in the existing `head_to_head(weekly_df)` output
       (all-time matchup history) — phrase as "X leads the series N-M" or "first-ever meeting"
       if the pair has no prior history.
     - Pre-format a `headline` string and a `blurb` string (1-2 sentences) in Python so the
       template just drops them in — mirrors the existing `fun_facts` string-building pattern in
       `general_stats()`.
   - **Upcoming section**: filter `team_season_df` to `year == current_year` and
     `upcoming_week.notna()`; same dedupe-by-pair approach; build `{home: {...}, away: {...}}`
     (no scores — game hasn't happened; maybe a short preview blurb using h2h history only).
   - **Standings sidebar**: reuse `current_season_snapshot(team_season_df, weekly_df,
     current_year)` (already sorted by standing) — pass through as-is or a trimmed subset of
     columns (rank, manager, record, points_for) for a compact sidebar list.
   - Return `{"week": int | None, "recaps": [...], "upcoming_week": {...} | None, "standings":
     [...]}`.
5. `espn_league_stats/main.py` (*depends on step 4*) — call `weekly_report(team_season_df,
   weekly_df, config.current_year)`; pass result as new `weekly_report` arg to
   `write_html_report(...)`.
6. `espn_league_stats/reports/html_report.py` — add `weekly_report: dict` param to
   `write_html_report`'s signature; pass straight through to `template.render(...)` as
   `weekly_report=weekly_report`.

### Phase C: New "Weekly Report" tab UI (newspaper style)
7. `espn_league_stats/reports/templates/index.html.j2` (*depends on step 6*):
   - Add a new `.tab-radio` input + `.tab-button` label following the exact existing pattern
     (hidden radio + label + `.tab-panel` div).
   - New `.tab-panel` laid out like a newspaper page:
     - Masthead-style header, e.g. "The Guarcino Gazette — Week {{ weekly_report.week }}
       Edition" in a serif display font.
     - Main column: one story block per matchup — bold serif headline, then the blurb
       paragraph (record/streak/h2h sentence), with the final score shown smaller beneath/
       beside it.
     - Sidebar box (float/grid column): "League Standings" through the latest week, compact
       numbered list (rank · manager · record · PF).
     - "This Week" preview section below/aside the recaps, lighter-weight styling (shorter
       blurbs, no scores).
     - Placeholder copy when a section is empty: "Season hasn't started yet — check back after
       Week 1!" / "Season complete — see you next year!".
   - New CSS block: serif font-family for headlines (e.g. Georgia/Times New Roman stack),
     newspaper column layout (CSS grid/flex: main column + sidebar), column-rule divider,
     consistent with existing dark theme (dark background, light serif text) rather than
     literal black-on-white.

## Relevant files
- `espn_league_stats/models.py` — `TeamSeasonStats` dataclass (add 2 optional fields)
- `espn_league_stats/extract.py` — `extract_team_season()`, reuse `_opponent_id_and_score()`
- `espn_league_stats/aggregate.py` — `build_team_season_df()` (add 2 columns), new
  `weekly_report()` function (model dedupe-pairing after `head_to_head()`'s pattern if reusable)
- `espn_league_stats/main.py` — orchestration, add call + pass-through arg
- `espn_league_stats/reports/html_report.py` — `write_html_report()` signature + render call
- `espn_league_stats/reports/templates/index.html.j2` — new tab radio/label/panel + CSS

## Verification
1. Regenerate via `.\.venv\Scripts\python.exe run.py --no-csv 2>&1 | Select-String -Pattern
   "error|Error|Traceback"` — confirm no errors/tracebacks.
2. Grep the output HTML for the new tab, confirm recap paragraphs render with real scores/
   records/streaks/h2h, and the upcoming-week preview has no scores, with no duplicate/mirrored
   matchups (the dedupe-by-pair logic is the main risk spot).
3. Manually eyeball a couple of recaps for correct winner/loser attribution and sensible margin
   wording (blowout vs. nailbiter thresholds).
4. Confirm cache round-trip: a cached past-season JSON (missing the two new fields) still loads
   fine via `TeamSeasonStats.from_dict` (defaults kick in).

## Scope boundaries
- Included: last completed week's recaps + next week's schedule preview + standings sidebar, for
  the current season only.
- Excluded: playoff-round labeling (per decision above — just "Week N"); a browsable archive of
  all past weekly reports (only most-recent + next); explicit bye-week UI treatment beyond
  silently excluding self-paired rows (byes are rare/nonexistent given even team counts per
  season historically, but the dedupe logic guards against crashing on one if it occurs).

## Demo / mockup

```
THE GUARCINO GAZETTE — Week 4 Edition

Justin Cerilli Downs Brad Cerilli, 142.6–118.3
Justin Cerilli rolled past Brad Cerilli by 24.3 points, extending his win streak to
three games (W3) and improving to 3-1-0 on the season. Justin now leads their
all-time series 5-3.

Bryan Testa Edges Wiley Cerilli in a Nailbiter, 130.1–128.9
In the closest game of the week, Bryan Testa squeaked past Wiley Cerilli by just 1.2
points, snapping a two-game skid and moving to 2-2-0 on the year. Wiley still holds
a 6-4 edge in their head-to-head history.

Sidebar — League Standings (through Week 4):
1. Justin Cerilli   3-1-0  (568.2 PF)
2. Wiley Cerilli    3-1-0  (552.1 PF)
3. Bryan Testa      2-2-0  (511.4 PF)
...

This Week Preview — Week 5:
John Cerilli vs. Evan Cerilli · Peter Cerilli vs. Tyler Cerilli ...
```
