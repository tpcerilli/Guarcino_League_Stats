# Things to add with more credits

- make githubpages update every week at 5 AM on Tuesday.




# Future Considerations

## Hover Effects
- When your cursor goes over a row and column, highlight that row and column.
- Maybe even add a functionthat will highlight that row when clicked.

## Best Game stats

Add in a way to view the scores for that team's best games. May require saving all 
games.


# Known data quirks

## 2011 championship (John Cerilli) — not in ESPN's data at all

The league existed in 2011, before ESPN's API history starts (2012-2026). John Cerilli
won that championship, but since there's no 2011 season data to correct, it can't be
handled the same way as the 2022 override below.

- Manually credited via `config/extra_championships.json` (`extra_championships`, keyed
  by manager_key/owner-id GUID), added on top of the ESPN-tracked count in `aggregate.py`.
- Reflected in the All-Time and Playoffs tabs' Titles column. There's no 2011 row/season
  anywhere else (Results By Season, Regular Season, etc.) since no such data exists.

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

## gh-pages now auto-deploys from main

A GitHub Actions workflow (`.github/workflows/deploy-gh-pages.yml`) rebuilds the
dashboard and pushes it to `gh-pages` automatically on every push to `main` — no more
manual branch-switching/copying. One-time setup required in the repo's GitHub Settings:

- Settings → Secrets and variables → Actions → add repo secrets `LEAGUE_ID`, `ESPN_S2`,
  `SWID` (same values as your local `.env`).
- Settings → Actions → General → Workflow permissions → set to "Read and write
  permissions" (needed for the action to push to `gh-pages`).
- Settings → Pages → Source should already be "Deploy from branch: gh-pages / (root)".

After that, just `git push origin main` and the live site updates within a minute or two.
