# Team report

| | |
|---|---|
| URL | `/raport-druzyny` (form), `/raport-druzyny/druk?club_id=&season_id=&last=15` (print, new tab) |
| View | `TeamReportFormView` (`pages/team_report.html`), `TeamReportPrintView` (`print/team_report.html`, `css/team_report_print.css`) |
| Menu | Reports › Team report; button "Team report <season>" on the team card |
| Code | `ehf/domain/team_report.py`, `ehf/infrastructure/team_report_reader.py`, `ehf/services/team_report.py` (+ `team_detail_*` for matches and lineups) |
| Database | as the team card, plus `match_team` (shots, 7m, 2') and other clubs' lineups of the previous season |

A printable team dossier for one season, designed for black-and-white printing: highlights are bold numbers on light grey, wins are filled circles, top scorers in the sheet are boxed. Missing `club_id`/`season_id`, a team without an edition in the season or `last` outside 1–40 → 400; unknown club → 404.

```
ONE PAGE (A4 portrait)
  logo  TEAM REPORT / <Team>                                   <season>
        country · competitions                  EHF match reports · as of <date>
  ─────────────────────────────────────────────────────────────────────
  Matches | W–D–L | Goals ±diff | Per match | GK save% / opp. | Top scorer | Last 5   (one low line)
  (1) Seasons — up to the chosen season; season rows + competition rows; current row shaded
  (2) Players — groups: Goalkeepers, Line players, Backs, Wings (then shirt number)
      No | Player | Born | Nat | Pos ‖ <season>: M G Avg Sh% 2' Saves Sv% ‖ <previous>: M G Avg Sv% | Club · competition
      Nat: IOC code (ehf.country, else domain/nationality.py); a second nationality shows as "+"
      Club · competition: "same club" / "same club · <other competition>" / "<other club> · <competition>" (italic) / "no EHF matches"
      highlighted: top 3 scorers, top 3 Sh% (min. 20 shots), best Sv% (min. 50 shots faced), top 3 scorers last season
  (3) Last N matches (default 15, up to the end of the season, across seasons), one line each
      Date | Competition · phase | H/A | Opponent | Score | W/D/L | G/Sh | 7m | 2' | GK Sv% | Opp. | Top scorers
      rows tinted by result in grey levels: win grey, draw light grey, loss white
```

The season sheets are a separate print: [zestawienie_sezonu.md](zestawienie_sezonu.md).

Fit: a small script measures the page and scales its content (`zoom`, not below 60 %) when it is taller than the printable area less 5 % (print layout runs slightly taller than screen).

Goalkeeper numbers skip matches where every goalkeeper of both teams has 0 saves (import gap).
