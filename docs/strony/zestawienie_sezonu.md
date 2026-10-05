# Season sheets

| | |
|---|---|
| URL | `/zestawienie-sezonu` (form), `/zestawienie-sezonu/druk?club_id=&season_id=` (print, new tab) |
| View | `TeamReportFormView(kind="sheets")` (`pages/season_sheets.html`), `SeasonSheetsPrintView` (`print/season_sheets.html`, `css/team_report_print.css`) |
| Menu | Reports › Season sheets; button "Season sheets" on the team card |
| Code | `TeamReportService.season_sheets()` in `ehf/services/team_report.py`, `SeasonSheets` / `SeasonSheetPage` in `ehf/domain/team_report.py`, `season_sheet()` in `ehf/domain/team_detail.py` |

Two A4 landscape pages: the chosen season (default: the latest) and the season before it. When the team did not play in EHF competitions in the previous season, its page says so; when no previous season exists in the database, only one page is printed. Missing `club_id`/`season_id` or a team without an edition in the chosen season → 400; unknown club → 404.

```
A4 LANDSCAPE, one page per season
  <Team>                         SEASON SHEET                         <season> · as of <date>
  Season sheet <season>   competitions · N matches · W–D–L · goals
  Player | Pos | <match columns: opponent + date (vertical), H/A, score> | M | G | Sh% | 2' | Sv%
  rows: goalkeepers, line players, backs, wings (then goals)
  cell: goals (′ = 2 min, R = red); goalkeepers saves/shots (+goals); empty striped = not in the lineup
  match top scorer boxed; header score underlined = win
  Team row: goals and goalkeeper save% per match
```

More than 20 players → denser rows; the fit script scales a page down (not below 60 %) if it is still too tall.
