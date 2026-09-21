# Player details

| | |
|---|---|
| URL | `/zawodnicy/<id>` |
| View | `PlayerDetailView` (`pages/player_detail.html`) |
| Menu | from Players list |
| Code | `ehf/interface/player_views.py` |
| Database | `ehf.person`, `person_nationality`, `match_lineup`, `match_player_stat`, `match_goalkeeper_stat` |

```
Start › Data › Players › Details
Player details #id

[ Hero ]
  photo  Name
         Pos
         chips: year, height, weight, nationality

[ Tabs ]
  Profile | Seasons & teams | Matches

[ Profile ]
  Field | Value
  name, position, birth, height, weight, nationality, EHF id

[ Seasons & teams ]
  Season | Competition | Team | M | G | Sh | % | Y | 2' | R | Saves | Faced | Save%
  one row per season + competition + club
  click a column header to sort

[ Matches ]
  Filters: Season, Competition, Club, Date  (+ pagination)
  Date | Season | Competition | Team | Opponent | Score | G | Sh | % | 2' | Saves | Faced | Save% | Details
  click a column header to sort all matching matches
  Details → /mecze/<id>
  double-click row → match details modal
```
