# Referees

| | |
|---|---|
| URL | `/sedziowie` |
| View | `RefereeListView` (`pages/referees.html`) |
| Menu | Data › Referees |
| Code | `ehf/interface/referee_views.py` |
| Card | `/sedziowie/<id>` |
| Database | `ehf.match_official` (`role = 'referee'`) |

Identity is `(display_name, first_name, last_name, country_code)`. The card id is `MIN(id)` of that group. City is not stored.

```
Start › Data › Referees
Referees
Officials of EHF matches.

[ Filters ]
  Search: [____________]   Country: [____________]
  [Filter]  [Clear]

[ Table ]
  ID | Name | Country | Matches | Actions
  click a column header to sort all matching referees
  Actions: Details → /sedziowie/<id>
```
