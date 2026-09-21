# Matches

| | |
|---|---|
| URL | `/mecze` |
| View | `MatchListView` (`pages/matches.html`) |
| Menu | Data › Matches |
| Code | `ehf/interface/match_views.py` |
| Card | `/mecze/<id>` — [mecz.md](mecz.md) |
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
  ID | Date | Time | Season | Competition | Phase | Home | Score | Away | Venue | Details
  Phase = phase, group in the same cell: "Group Phase (A)", "Last 16"
  click a column header to sort all matching matches (again = reverse)
  ---+------+------+--------+-------------+------+-------+------+-------+--------
  rows from ehf.match

  Score: score_home:score_away
  result_type suffix when not normal: walkover | extra_time | penalties
  status: played | awarded | scheduled_or_no_result

  Details → /mecze/<id>
  double-click row → modal with the same match details page
```
