# Match details

| | |
|---|---|
| URL | `/mecze/<id>` |
| View | `MatchDetailView` (`pages/match_detail.html`) |
| Menu | from Matches list |
| Code | `ehf/interface/match_views.py` |
| Database | `ehf.match`, `match_period`, `match_team`, `match_lineup`, `match_player_stat`, `match_goalkeeper_stat`, `match_team_official`, `match_official`, `match_metric`, `match_action`, `match_action_actor`, `person.profile_position`, `club.country_code` |

```
Start › Data › Matches › Details
Match details #id

[ Hero above tabs ]
  Home                    SCORE                 Away
  LUX                     HT / result_type      SRB
  home                                          away
  Home / Away names → /druzyny/<club_id> (click → modal, double-click → new tab)

[ Tabs ]
  Basic data | Team statistics | Lineup | Play-by-play

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
  Player → /zawodnicy/<person_id>, team name in header → /druzyny/<club_id>
  click → modal, double-click → new tab (plain text when id is missing)
  order and tint by group: GK, LP (pivot), backs, wings
  max goals in each team in red (ties too)
  under each team: GK saves, Shooting, 7m (x/y and %), Short-handed minutes (2' × 2)
  staff codes
  legend under both tables in the same group order

[ Play-by-play ]
  compact centre axis: home left, away right, clock and score in the middle column
  event type shown as a small badge (Goal, Save, Turnover, 2 min, Yellow, Red, 7m, Timeout)
  goal: scorer, zone, assist, GK who conceded; save: GK + shooter
  10:00 / 20:00 separators show the score then
  markers: first lead of each side, highest lead (margin ≥ 2), highest level score
  analytics charts above the list (shared home/away colours):
    Lead margin — goal difference 0–60 min, green/red bands, HT, max leads, final margin
    Score progression — cumulative goals for both teams, HT, final totals
    Goals by 5-minute period — grouped bars with values
  filters: All | Goals | Shots | Saves | Turnovers | Cards | 7m | Timeout
  click a player name to highlight that person's events; click again to clear
  pauses, duplicate 2 min / yellow / red echoes and technical-error twins are hidden
  empty state when the match has no ehf.match_action rows
```
