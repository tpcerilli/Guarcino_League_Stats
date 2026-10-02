# Future Considerations

- Colors on line graphs are too similar.
- When the user first clicks the title column, always sort high to low first or (best to worst)

## Playoff Stats

Add Reg Season finish column. Put this in before Final Standing

## Current Season Tab Additions

Could add some of the misc stats to the current season tab. These could be separate 
tables from the main one.

## Always sort secondarily by PF

Like when wins are tied sorting high to low, sort the person with more PF first.

## Workflow to update gh-pages
 
I dont like that when i change things on main, the gh-pages doesn't update as well. I'd like a better flow than this. I don't want to have to update in two places at once.

## Best Game stats

Add in a way to view the scores for that team's best games. May require saving all 
games.

## New table/tab General Stats

Add in general stats, such as:
- Title wins by regular season finish. Could make a table showing reg season finish vs playoff finish.
- Title wins by PF ranking. Could make a table showing PF season finish vs playoff finish.
- Could also add title wins by # acquisitions rank by season.



# Known data quirks

## 2022 championship override (Bryan Testa) — not reflected in ESPN's own data

ESPN's platform never recorded Bryan Testa as the 2022 champion. That year's finals
ended in a forfeit by Wiley Cerilli, handing Bryan the title by league ruling, but
ESPN's `final_standing` field still shows Wiley as 1st and Bryan as 2nd.

- Corrected via `config/standings_overrides.json` (`final_standing_overrides.2022`:
  team_id 4 → 2, team_id 8 → 1), applied in `aggregate.py` on top of the raw ESPN data.
- All derived stats (championships count, Misc/Playoffs tabs, gold/silver row
  highlighting, Results By Season) use the corrected standing, not ESPN's raw value.
- If ESPN ever updates their own record for that season, double check this override
  doesn't double-correct it.

## 2018 PF/PA mismatch between All-Time and Regular Season tabs (~6-7 points)

All-Time pulls points_for/points_against from ESPN's frozen season-aggregate field
(`team.points_for`/`points_against`). Regular Season/Playoffs instead sum each team's
individual weekly scores from the schedule. These two sources agree exactly for every
season except **2018**, where they differ by 6-7 points per team (both PF and PA).

- Isolated to 2018 only — every other season (2012-2026) matches exactly.
- Symmetric across opponents: when one team's PF is off by -7, that week's opponent
  shows a matching PA discrepancy, so it traces to one specific 2018 matchup's score,
  not a bug in our aggregation code.
- Likely cause: 2018 predates ESPN's 2019 API platform migration; probably a stat
  correction applied to one week's score after the season-aggregate total was already
  locked in, updating one source but not the other.
- Impact is negligible (~0.03% of career total points) and not worth "fixing" by
  picking one source as authoritative, since both are genuine ESPN-reported numbers —
  just from two different fields that happen to disagree for this one season.
