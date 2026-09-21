# Referee details

| | |
|---|---|
| URL | `/sedziowie/<id>` |
| View | `RefereeDetailView` (`pages/referee_detail.html`) |
| Menu | from Referees list |
| Code | `ehf/interface/referee_views.py` |
| Database | `ehf.match_official` (`role = 'referee'`), `match` |

Names stay as stored. City is not stored. Statistics use played matches only.

Counting: one row per match; each team gets one appearance; the partner is never the same referee and is counted once per shared match.

```
Start › Data › Referees › Details
Referee details #id

[ Hero ]
  Display name
  Country
  chips: matches, seasons, competitions

[ Tabs ]
  Data | Matches | Statistics

[ Data ]
  ID, display name, first name, last name, source name, country
  first match, last match
  Summary: matches, played matches, seasons, competitions, teams
  Activity by season: Season | Matches | Competitions

[ Matches ]
  Filters: Season, Competition, Club, Side, From, To  (+ pagination)
  default sort: newest first
  Date | Season | Competition | Home | Score | Away | Partner | Details
  Partner → /sedziowie/<partner_id>
  Details → /mecze/<id>
  double-click row → match details modal

[ Statistics ]
  seasons, competitions, season × competition
  teams, home teams, away teams
  partners
  months, weekdays, season × month
  distinct teams / competitions
  TOP 10 + Show all
  HTML/CSS bars and heatmap
```
