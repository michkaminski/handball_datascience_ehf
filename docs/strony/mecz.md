# Match details

| | |
|---|---|
| URL | `/mecze/<id>` |
| View | `MatchDetailView` (`pages/match_detail.html`) |
| Menu | from Matches list |
| Code | `ehf/interface/match_views.py` |
| Database | `ehf.match`, `match_period`, `match_team`, `match_lineup`, `match_player_stat`, `match_goalkeeper_stat`, `match_team_official`, `match_official`, `match_metric` |

```
Start › Data › Matches › Details
Match details #id

[ Hero ]
  Home                    SCORE                 Away
  home                    HT / result_type      away
  chips: competition, season, phase, group, kickoff, venue, status, spectators

[ Periods ]
  Period | Home | Away | Played

[ Team statistics ]
  Stat | Home | Away
  goals, shots, 7m, cards + match_metric rows

[ Lineup home | Lineup away ]
  # | Player | G | Sh | Y | 2' | R | Saves
  staff codes under the table

[ Officials ]
  Role | Name | Country
```
