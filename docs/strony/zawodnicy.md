# Players

| | |
|---|---|
| URL | `/zawodnicy` |
| View | `PlayerListView` (`pages/players.html`) |
| Menu | Data › Players |
| Code | `ehf/interface/player_views.py` |
| Card | `/zawodnicy/<id>` — [zawodnik.md](zawodnik.md) |
| Database | `ehf.person`, `ehf.match_lineup`, `ehf.match_team`, `ehf.match` |

```
Start › Data › Players
Players
Players and match appearances in the selected range.

[ Filters ]
  Season: [select]  Competition: [select]  Club: [select]
  Position: [select]  Birth year: [select]  Search: [text]
  [Filter]  [Clear]

[ Table ]
  ID | First name | Last name | Pos. | Teams | Year | Height | Weight | Details
  click a column header to sort all matching players
  rows: persons with at least one match_lineup
  Pos. = GK, LW, CB, …

  Details → /zawodnicy/<id>
```
