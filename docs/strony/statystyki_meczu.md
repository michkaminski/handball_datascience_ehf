# Match statistics (tab "Statistics" on the match card)

| | |
|---|---|
| URL | tab on `/mecze/<id>`; content read from `/mecze/<id>/statystyki` (HTML fragment) the first time the tab is opened |
| View | `MatchStatisticsView` (`partials/match_statistics.html`), tab in `pages/match_detail.html` |
| Shown | only when the match has a play-by-play (`ehf.match_action`); the fragment alone says so for other matches |
| Code | `ehf/domain/match_statistics.py` (player and team metrics), `ehf/domain/match_summary.py` (shared rules, baseline), `ehf/services/match_summary.py` (`MatchSummaryService.statistics`), `ehf/infrastructure/match_summary_reader.py` (actions, lineup, reference matches), `ehf/interface/match_statistics_charts.py` (chart geometry, KPI cards) |
| Script | `static/js/match_detail.js`: `MatchTabs.load` (lazy load, also inside the match modal), `StatsBoard` (sub-tabs, player rows, link to Play-by-play) |
| Style | `.mst-*` in `static/css/admin.css`; home indigo `#4338ca`, away orange `#eb6834` — the same as Play-by-play and the A4 summary |
| Database | `ehf.match`, `match_team`, `club_edition`, `match_lineup`, `match_action`, `match_action_actor`, `match_ticker`, `competition_edition`, `season` |

The tab uses the same reading of the feed as the A4 summary and the Play-by-play tab: repeated events are
dropped, the 2021-22 fast breaks (sent four times) count once, the `TO`/`FB` companion row marks a fast
break, the 7 m shootout is left out of every figure.

## Layout

```
Statistics
  headline sentence (same rules as the A4 summary)
  [ Overview | Shooting | Goalkeepers | Line-ups ]

  Overview
    KPI cards: goals vs expected goals (xG) · shooting % · goalkeeper saves % · attack efficiency ·
               attacks (shots + turnovers); better value bold, Ø = competition average
    Win probability: home team's chance to win through the match (area above 50 % home colour,
               below away colour), half-time line, the three biggest swings numbered and listed
    Team comparison: both teams' bars from one baseline on one scale, | = competition average
    Shot outcomes: every shot of a team as one stacked bar — goal / saved / missed / post / blocked
    Numerical situations: goals scored : conceded with more and with fewer players on court

  Shooting (per team)
    court with the 8 zones: goals/shots, fill = conversion
    table: zone · shots · goals · % · Ø % of the competition · xG · goals − xG (green above, red below)
    click a zone (court circle or table row, also Enter): small window with the players who shot
      from there — player · shots · goals · %; closes with ×, Esc or a click outside

  Goalkeepers (one row per goalkeeper who faced a shot, grouped by team)
    save % · saves/shots on target · 7 m saves · GSAA
    meter: save % with the competition average marked, minutes of the first and last shot faced
    wide time axis (0'–60' labelled every 10'): every shot on target faced, filled = save,
      red ring = goal conceded
    "All goalkeepers" row per team (when more than one played): all of them added up
    charts (team total): save rate in successive 10-minute periods · cumulative GSAA momentum
      · goalkeeper vs shooter matrix (faced / saved / save %)

  Line-ups (one table per team, every player of the match sheet)
    order as in the Lineup tab: Goalkeepers, Line players, Backs, Wings, Other players (group rows),
      then shirt number
    No · Player · Pos (GK, LP, LB, CB, RB, LW, RW — position of the season, else of the profile) · Act. · G/Sh · % · xG · G−xG · 7m · As · G+A · FB · TO · ST · BL · 7mW · 2' (+ card)
    · Saves · GSAA · WPA · involvement strip (every action as a dot on 0'–60')
    best goals, assists and WPA bold; players without recorded actions greyed
    click / Enter on a player: details row
      actions count, first–last minute, goals in a close finish
      big strip + every action: clock · score · what · details (assist, zone, goalkeeper, shooter)
      "Show in Play-by-play": opens that tab, shows all events, highlights the player, scrolls to the first
```

Number and name columns stay fixed when the table scrolls sideways (phones); the win-probability chart
scrolls sideways under 700 px.

## Metrics

| Metric | How it is computed |
|---|---|
| Expected goals (xG) | each shot is worth the share of shots from its zone that were goals in the reference matches; fast breaks (old feeds) are a zone of their own; shots without a zone use the overall conversion |
| G − xG | goals minus expected goals — finishing (and the opponent's goalkeeping) above or below an average team |
| GSAA | goals saved above average: saves minus the saves an average goalkeeper of the competition makes on the same shots on target, zone by zone |
| WPA | win probability added by a player's goals, in percentage points: change of his team's win probability at each goal, summed |
| Close finish | a goal in the last 10 minutes when the margin before it was 2 or less |
| Attack efficiency | goals / (shots + turnovers); shown only when the feed has turnovers |
| Attacks (est.) | shots + turnovers (rebounds and free throws are not in the feed) |
| Act. | recorded actions of the player: shots, assists, saves and goals conceded (goalkeepers), turnovers, steals, blocks, 7 m won, 2 min, cards |

Reference matches (`Baseline`): played matches with a play-by-play of the same competition and season;
below 30 such matches the previous season joins. Computed once per set of matches and kept in memory
(`MatchSummaryService._baselines`).

Win probability: logistic model on lead / √(minutes left + 1) and a home edge fading with the clock,
fitted on 1682 EHF matches 2021–2027 (`WIN_LEAD`, `WIN_HOME` in `match_summary.py`).

## Feed limits

- turnovers exist from 2022-23 (most matches from 2023-24); without them TO, attack efficiency and attacks are empty
- fast breaks are marked only up to 2024-25
- assists depend on the ticker operator of the venue (no competition average for them)
- the goalkeeper on a shot is the one the feed names; a few shots have no goalkeeper, so team saves can differ by one from the sum of the goalkeepers
