# Matches

| | |
|---|---|
| URL | `/mecze` |
| View | `MatchListView` (`pages/matches.html`) |
| Menu | Data › Matches |
| Code | `ehf/interface/match_views.py` |
| Card | `/mecze/<id>` (skeleton) |
| Database | `ehf.match`, `ehf.match_period`, `ehf.match_team`, `ehf.club_edition`, `ehf.venue` |

Change the sketch here, then filters in `match_filters.py` and SQL in `match_list_reader.py`.

```
Start › Data › Matches
Matches
Compact match list. The table is the main element of the page.

[ Filters ]
  Season: [select]  Competition: [select]  Phase: [select]  Group: [select]
  Venue: [select]  Club: [text]  Date: [date]
  [Filter]  [Clear]

[ Table ]
  ID | Date | Time | Season | Competition | Home | Score | Away | Venue | Details
  ---+------+------+--------+-------------+------+-------+------+-------+--------
  rows from ehf.match

  Score: score_home:score_away
  result_type suffix when not normal: walkover | extra_time | penalties
  status: played | awarded | scheduled_or_no_result

  Details → /mecze/<id>
```
