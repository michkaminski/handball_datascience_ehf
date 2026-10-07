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
  Basic data | Team statistics | Lineup | Play-by-play | Statistics (only with a play-by-play)

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

[ Play-by-play ]   home indigo, away orange — the same colours and rules as the match summary print
  head: team key · ties · lead changes · biggest lead of each team (+N score · minute)
  Goal difference — one bar per minute (biggest difference reached in it; home up, away down,
    each side scaled to its own biggest lead), half-time line with score, biggest leads circled;
    hover a bar for minute · score · lead, click (or Enter) to jump the list to that minute
    the score every 5 minutes in a row under the time axis (coloured by the team in front)
  Score — running goals of both teams as steps, final totals at the line ends
  Goals per 10 minutes — paired bars with values (+ ET)
  filter pills: All events | Goals | Saves | Missed shots | Turnovers | Cards and 2 min | 7m awarded | Timeouts
  event list (scrolls inside its frame, team names and period headers stay on top):
    home events right-aligned against the centre column, away events left-aligned
    centre: clock and score; when a goal changes the score it sits in a pill of the scoring team
    badge per event (goal filled, save outlined in the team colour, 2 min / yellow, red, timeout, 7m)
    second line: assist, "past GK" (the goalkeeper who conceded), "shot by" for saves, fast break, zone
    dashed dividers with the score at 10', 20', 40', 50'; dark bars for half-time and full time
    click a player name to follow that person's events; click again to clear
  read like the summary: repeats of the same event are dropped (2021-22 fast breaks come four times),
  the TO/FB companion row marks the goal as a fast break, goalkeeper swaps and substitutions
  (GKS, SUBST) are hidden, pauses and duplicate 2 min / yellow / red / technical-error echoes too
  empty state when the match has no ehf.match_action rows
```

Statistics tab (Overview, Shooting, Goalkeepers, Line-ups): [statystyki_meczu.md](statystyki_meczu.md).
