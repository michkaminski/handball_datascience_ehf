# Venue details

| | |
|---|---|
| URL | `/hale/<id>` |
| View | `VenueDetailView` (`pages/venue_detail.html`) |
| Menu | from Venues list |
| Code | `ehf/interface/venue_views.py` |
| Database | `ehf.venue`, `match`, `match_lineup`, `match_player_stat` |

Played matches: `status = 'played'`, not a walkover, `result_type <> 'walkover'`.
Address and capacity are not in the source. Hall fill is not calculated; attendance completeness is always shown.

```
Start › Data › Venues › Details
Venue details #id

[ Hero ]
  Name
  City (Country)
  chips: played, seasons, competitions

[ Tabs ]
  Data | Matches | Players | Statistics

[ Data ]
  ID, name, city, country, first match, last match
  Summary: matches, played matches, seasons, competitions, teams, players

[ Matches ]
  Filters: Season, Competition, Club  (+ pagination)
  Date | Season | Competition | Home | Score | Away | Details
  played matches only
  Details → /mecze/<id>
  double-click row → match details modal

[ Players ]
  Filters: Search  (+ pagination)
  Player | Matches | First | Last | Goals | Avg | Teams | Details
  Details → /zawodnicy/<id>

[ Statistics ]
  seasons, competitions, result profile
  mean / median goals, histogram
  months, weekdays, season × month
  attendance + completeness (no invented fill %)
  match records
  top teams, top appearances, top scorers
  TOP 10 + Show all
  HTML/CSS bars and heatmap
```
