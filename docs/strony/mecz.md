# Match details

| | |
|---|---|
| URL | `/mecze/<id>` |
| View | `MatchDetailView` (`pages/match_detail.html`) |
| Menu | from Matches list |
| Code | `ehf/interface/match_views.py` |
| Database | `ehf.match`, `match_period`, `match_team`, `match_lineup`, `match_player_stat`, `match_goalkeeper_stat`, `match_team_official`, `match_official`, `match_metric`, `person.profile_position`, `club.country_code` |

```
Start › Data › Matches › Details
Match details #id

[ Hero above tabs ]
  Home                    SCORE                 Away
  LUX                     HT / result_type      SRB
  home                                          away

[ Tabs ]
  Basic data | Team statistics | Lineup

[ Basic data ]
  chips: competition, season, phase, group, kickoff, venue, status, spectators
  click a column header to sort any table
  [ Periods ]
    Period | Home | Away | Played
  [ Officials ]
    Role | Name | Country

[ Team statistics ]
  Stat | Home | Away
  goals, shots, 7m, cards + match_metric rows

[ Lineup home | Lineup away ]
  # | Player | Pos | G | Sh | % | Y | 2' | R | Saves | Faced | Save%
  Pos = GK, LW, RW, LB, RB, CB, LP, …
  order and tint by group: GK, LP (pivot), backs, wings
  max goals in each team in red (ties too)
  under each team: GK saves, Shooting, 7m (x/y and %), Short-handed minutes (2' × 2)
  staff codes
  legend under both tables in the same group order
```
