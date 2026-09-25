# Scorers

| | |
|---|---|
| URL | `/strzelcy` |
| View | `ScorerListView` (`pages/scorers.html`) |
| Menu | Data › Scorers |
| Kod | `ehf/interface/scorer_views.py` |
| Baza | `ehf.match_player_stat`, `ehf.match_lineup`, `ehf.person` |

Only played matches (`PLAYED_SQL`). Rank is always by total goals in the filter scope.

Change the sketch here, then filters in `scorer_filters.py` and SQL in `scorer_list_reader.py`.

```
Start › Data › Scorers
Scorers
Goal scorers in the selected season and competition.

[ Filters ]
  Season: [select]  Competition: [select]
  [Filter]  [Clear]

[ Table ]
  Pos. | Player | Team | Goals | Matches | Details
  Pos. = rank by goals in the whole filter (not only the page)
  click a column header to sort the table (Pos. stays goal rank)
  Matches = played appearances with match statistics

  Player name → /zawodnicy/<id>
  Details → /zawodnicy/<id>
  double-click row → modal with the same player details page
```
