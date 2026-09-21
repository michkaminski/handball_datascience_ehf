# Match details

| | |
|---|---|
| URL | `/mecze/<id>` |
| View | `MatchDetailView` (`pages/match_detail.html`) |
| Menu | from Matches list |
| Code | `ehf/interface/match_views.py` |
| Database | `ehf.match`, `match_period`, `match_team`, `match_lineup`, `match_player_stat`, `match_goalkeeper_stat`, `match_team_official`, `match_official`, `match_metric`, `person.profile_position`, `player_edition.profile_position` |

```
Start › Data › Matches › Details
Match details #id

[ Hero ]
  Home                    SCORE                 Away
  home                    HT / result_type      away
  chips: competition, season, phase, group, kickoff, venue, status, spectators

[ Periods ]
  Period | Home | Away | Played

[ Tabs ]
  Team statistics | Lineup

[ Team statistics ]
  Stat | Home | Away
  goals, shots, 7m, cards + match_metric rows

[ Lineup home | Lineup away ]
  # | Player (position) | G | Sh | Y | 2' | R | Saves | Faced | Save%
  row tinted by position hue
  max goals in each team in red (ties too)
  staff codes under the table

[ Officials ]
  Role | Name | Country
```
