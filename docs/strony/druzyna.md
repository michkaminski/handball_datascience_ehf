# Team details

| | |
|---|---|
| URL | `/druzyny/<id>` (`id` = `ehf.club.id`), `?tab=basic|seasons|matches|players|goalkeepers|sheet` |
| View | `TeamDetailView` (`pages/team_detail.html`) |
| Menu | from Teams, Matches, Match details (click → modal, double-click → new tab) |
| Code | `ehf/domain/team_detail.py` (rules), `ehf/infrastructure/team_detail_reader.py` (SQL), `ehf/services/team_detail.py` |
| Database | `ehf.club`, `club_edition`, `country`, `match`, `match_team`, `match_lineup`, `match_player_stat`, `match_goalkeeper_stat`, `player_edition`, `venue` |

Modelled on the team card in `handball_datascience` (tabs 1–5 + season sheet). Charts (Summary, Form) are not done yet.

Rules:
- W/D/L from the regular-time score (`full_time_*`, else `score_*`); draws after extra time / penalties counted as decided draws.
- Walkovers and matches without a result are "Other", not in the goal record.
- Spectators: played matches with known attendance; 0 counts, NULL does not.
- Goalkeepers: only lineup rows with `shots_faced > 0`. Save% = Σ saves / Σ shots faced.
- Matches where every goalkeeper of both teams has 0 saves have no save data (import gap, mostly 2022-23) — skipped in GK numbers.

```
Start › Data › Teams › Details
<Team name>
Team card #id · gender · seasons X – Y
[Back to list]                                  [EHF profile]

[ Hero ] logo, name, country, chips: seasons, matches, GK save%

[ Tabs ] Basic data | Seasons | Matches | Players | Goalkeepers | Season sheet

[ Basic data ]
  KPI: seasons, range, matches, names, GK save%, opponents' GK save%
  Attendance home / away: avg, median, total, record (→ match), coverage
  Fields: ID, EHF id, name, gender, country, address, website
  Name history | Home venues (→ /hale/<id>)
  Season entries: season, competition, name → Season sheet, Players

[ Seasons ]
  Season | Competition | Name | M W D L Win% Goals Diff AvgFor AvgAg DecidedDraws Other Spect(home avg, away avg, home sum)
  season row + competition rows when a season has several competitions

[ Matches ]  filters: season, competition, opponent, finished only
  KPI: matches, W-D-L, win%, goals, diff, GK save% / opponents
  Attendance in range
  Date | Season/competition | Phase | H/A | Opponent → team | Team score | Result | Match score | GK save% | Opp. GK save% | Spectators | Details

[ Players ]  filters + player name; client-side sort
  # | Player → card | Pos | M G Avg Sh Shot% Y 2' R Saves Faced Save% | Seasons | Last match

[ Goalkeepers ]  filters: season, competition, opponent
  KPI: matches with GK data, saves/faced, save%, opponents' save%, difference, saves per match
  Records: best / worst match (min. 10 shots), most shots faced, best save% (min. 100 shots)
  Goalkeepers: # | GK | M | Saves | Faced | Save% | Saves/match | Median match save% | Best match | Seasons
  By season (+ competition): team saves/faced/% vs opponents saves/faced/%
  Match by match: date, H/A, opponent, score, GKs saves/faced, team %, opponents saves/faced, %

[ Season sheet ]  season (required, default latest), competition, opponent
  rows = players (GK, LP, backs, wings; then goals), columns = matches with a team lineup
  cell: goals, 2′/Y/R, GK saves/faced; totals: M, G, Shot%, Cards, Saves, Save%; footer = team total
```
