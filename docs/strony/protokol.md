# Match sheet

| | |
|---|---|
| URL | `/protokol` (form), `/protokol/druk` (A4 print, new tab) |
| View | `MatchSheetFormView` (`pages/match_sheet.html`), `MatchSheetPrintView` (`print/match_sheet.html`, `css/match_sheet_print.css`) |
| Menu | Reports › Match sheet (top bar: Reports) |
| Code | `ehf/domain/match_sheet.py` (rules), `ehf/infrastructure/match_sheet_reader.py` (SQL), `ehf/services/match_sheet.py` |
| Database | `ehf.season`, `club_edition`, `club`, `match`, `match_team`, `match_lineup`, `match_player_stat`, `match_goalkeeper_stat`, `player_edition`, `person`, `venue` |

Modelled on the ZPRP match protocol in `handball_datascience` (`/administracja/terminarz/<id>/protokol`), but the user picks any two teams instead of a scheduled match. Standalone HTML, printed or saved as PDF from the browser (no WeasyPrint here).

The live HTML protocol (`print/protokol_live.html`, ZIP with HTML + JSON) is a copy of `src/handball/interface/templates/admin/schedule/protocol_live.html` in `handball_datascience`; its behaviour (including goalkeeper saves: goalkeeper in goal, "+ OBRONA", goalkeeper credited with each conceded goal, saves / on-target shots and %) is described there in `protocol_live.md`. Keep both files identical.

Parameters of `/protokol/druk`: `season_id`, `home_id`, `away_id` (required, different), `competition_id`, `date`, `time`, `venue_id` (default: the home team's usual venue), `order=positions|numbers`, `previous=1`. Missing/invalid → 400.

Rules:
- Squad = players in the team's lineups in the season (all competitions), before `date` when given. `previous=1` adds last season's players who have not played yet ("–" in M, G, Avg). No lineups → registered roster from `player_edition` (0, 0, "–") with a note.
- Number and position: from the newest lineup that has them. P: G goalkeeper, B back, W wing, P pivot.
- Bold goals: team's top 4 scorers, ties share the place (1, 1, 1, 4); zeros never.
- Sv%: goalkeepers only, Σ saves / Σ shots faced; matches where every goalkeeper of both teams has 0 saves are skipped (no save data).
- Order `positions`: GK, pivots, backs, wings, others, then shirt number; thick line between groups. `numbers`: shirt number only.
- Row height = 173 mm / all players − 0.2 mm, kept in 3.0–5.2 mm; font 1.6 × height pt, max 8.5 pt — one A4 page (checked: 37 and 49 players).

```
+----------------------+------------------+-----------------------------------+
| A Home team          | Competition      | Venue (address)                   |
| B Away team          | season · date    | [  ]:[  ]  [  ]:[  ]  [      ]    |
+----------------------+------------------+-----------------------------------+
| A (name) Team    CTRY        | Penalties   | Match progress                |
| No | Name | P Yr M G Avg Sv% | Y 2' 2' 2' R B | 1st half | 2nd half      |
| … squad (groups by position) …             | T | A | score | B  ×2 halves |
| A–E team officials | Y 2' R                | … 34 empty rows …             |
| B (name) … same …                          | 7-metre throws A / B          |
+--------------------------------------------+-------------------------------+
| Officials: referee ×2, EHF delegate, timekeeper, scorekeeper | remarks | final score / half-time / winner |
+-----------------------------------------------------------------------------+
                                                            legend · source
```
