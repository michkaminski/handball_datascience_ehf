# Match summary

| | |
|---|---|
| URL | `/mecze/<id>/podsumowanie` (print, new tab; Polish), `…?lang=en` (English) |
| View | `MatchSummaryPrintView` (`print/match_summary.html`, `css/match_summary_print.css`) |
| Menu | buttons "Match summary (A4) · PL" and "EN" on the match card (only when the match has a play-by-play); PL / EN switch in the screen bar |
| Code | `ehf/domain/match_summary.py`, `ehf/infrastructure/match_summary_reader.py`, `ehf/services/match_summary.py`, `ehf/interface/match_summary_charts.py`, `ehf/interface/match_summary_texts.py` (wording PL/EN) |
| Database | `ehf.match`, `match_team`, `club_edition`, `venue`, `match_action`, `match_action_actor`, `match_ticker` |
| Export | `python scripts/export_match_summary.py <id> [<id> …] [--lang pl / en / both] [--variant full / short / both]` → `match_<id>_<lang>.pdf/.png` (needs the app running) |

A one-page statistical story of a match, read from the play-by-play feed. The domain returns keys and a
structured headline (`Headline`); every word on the page comes from `match_summary_texts.py`. Home is indigo, away orange
(they stay apart in greyscale). No ticker → 404. The page scales itself down (`zoom`, not below 75 %)
when a long scorer list does not fit.

```
ONE PAGE (A4 portrait)
  logo  HOME            25 : 24            AWAY  logo
                HT 13:15 · after extra time / 7 m shootout
  competition · phase · group · kickoff · venue · spectators
  headline sentence generated from the flow (comeback / control / go-ahead goal / draw / shootout)
  (1) How the match went
      goal difference over time (home above, away below), half-time line, scoring runs 3:0+ shaded,
      T = timeouts, 2' / R = suspensions and red cards, ①②③ = the three biggest win-probability swings
      home win probability under it; key moments listed below the chart
  (2) Team comparison      butterfly bars + Ø competition average (same competition, this season;
                           the previous one joins below 30 matches); better value bold
      shooting, attack efficiency (goals / (shots + turnovers)), goalkeeper saves, 7 m, fast-break goals,
      assisted goals (no average: depends on the ticker operator), turnovers, steals, blocks, 2'
  (3) Phases               goals per 10 minutes (+ ET), goals with more / fewer players on court,
                           timeouts with goals 3 minutes before → after
  (4)(5) per team          shot map by zone (fill = shooting %), wings / 6 m / 9 m / 7 m / fast break,
                           its goalkeepers: saves / shots, %, 7 m (bold: above the competition average)
  (6)(7) per team          scorers: G/Sh, %, 7 m, assists, turnovers, 2', a strip with when the goals came;
                           a line with players who shot without scoring and assist-only players
  facts                    ties, lead changes, time in front, biggest lead, best run,
                           longest without a goal, last 10 minutes
                                                                              Sportomatyka „Bawimy się danymi”
```

Feed differences the domain handles (`ehf/domain/match_summary.py`):

- 2021-22 sends a fast-break goal four times (zones `FB`, `FBL`, `FBR`, `FBC`) → one shot, marked fast break.
- up to 2024-25 a fast-break shot is followed by a `TO` row with `action_add = 'FB'` → a fast-break mark, not a turnover.
- turnovers exist from 2022-23 (most matches from 2023-24); without them the attack-efficiency row and the TO column are hidden.
- fast breaks are not marked from 2025-26 → the fast-break row is hidden.
- the 7 m shootout (`PSO`) is left out of every figure; the headline names the score before it.

Win probability: logistic model on lead / √(minutes left + 1) and a home edge fading with the clock,
fitted on 1682 EHF matches 2021–2027 (`WIN_LEAD`, `WIN_HOME`).

## Short version (`?variant=short`)

The same page without club crests, competition averages, key moments and shot maps. "How the match went"
is one bigger bar chart instead of goal difference + win probability: one bar per minute showing the biggest
goal difference reached in that minute (home up, away down; each side scaled to its own biggest lead), and
the biggest lead of each team marked with "+N score · minute"; the attack-by-zone
block becomes a goalkeeper table per team (saves / shots, %, a 0–100 % bar, 7 m, team total). Also left out:
the phase in the meta line, the timeout list under "Phases", the assisted-goals and blocks rows of the
comparison, and the facts "time in front", "best run", "longest without a goal", "last 10 minutes". Team comparison draws both teams' bars from one baseline on one scale
(percentages on 0–100 %), so their lengths compare directly. The competition average is not read
for this version. Buttons "Short summary · PL" / "EN" on the match card; export with `--variant short`
(files `match_<id>_short_<lang>.pdf/.png`).
