# Attendance

| | |
|---|---|
| URL | `/raporty/frekwencja` |
| View | `AttendanceAnalyticsView` (`pages/attendance_analytics.html`) |
| Menu | Reports › Attendance |
| Code | `ehf/domain/attendance_analytics.py`, `attendance_opponents.py`, `attendance_calendar.py`, `attendance_extended_records.py`, `attendance_science.py`, `attendance_forecast.py`, `attendance_cities.py`, `attendance_city_breakdown.py`, `attendance_city_names.py`; `ehf/services/attendance_analytics.py`; `ehf/infrastructure/attendance_analytics_reader.py`, `attendance_extended_queries.py`, `attendance_cities_queries.py`, `attendance_city_breakdown_queries.py`, `attendance_city_breakdown_queries.py`, `attendance_sample_query.py`; `ehf/interface/attendance_analytics_views.py`, `attendance_analytics_filters.py`, `attendance_analytics_chart.py` |
| Assets | `static/js/attendance_analytics.js`, `.att-*` rules in `static/css/admin.css` |
| Database | `ehf.match.spectators` (nullable), `ehf.match`, `competition_edition`, `season`, `competition`, `club_edition`, `venue` |

```
Start › Reports › Attendance
Attendance
Spectators of played matches. Matches without known attendance are excluded from averages.

[ Filters ]   GET, all optional
  Season | Competition | Gender (men/women) | Phase | Home club
  Date from | Date to | [x] Exclude zeros
  [Filter]  [Clear]

[ Tabs ]  .match-tabs, role=tablist, data-attendance-tabs
  Overview | Trends | Clubs | Cities | Records | Opponents | Calendar | Extended records | Data science
  data-tab: overview trends clubs cities records opponents calendar extended science
  panels: section#att-panel-<data-tab>[data-attendance-panel]; only the active panel is visible
  ?tab=<data-tab> selects a tab on load; switching a tab updates the URL with history.replaceState
  charts are drawn the first time their panel is shown (hidden panels have no size)
  filters and the page head stay above the tabs

[ Overview ]                                             #att-panel-overview
  Total spectators | Matches with attendance | Played matches | Coverage
  Mean per match   | Median per match        | Record attendance (→ match) | Mean YoY
  completeness notes (unknown ≠ 0, zeros, no capacity → no fill rate)

[ Seasonal trends ]                                      #att-panel-trends
  linear trend of the mean (per season, x = season start year)
  chart trend:    bars = mean, whiskers = Q1–Q3, line = 3-season moving average
  chart coverage: bars = matches with known attendance, line = coverage % of played matches
  Season | Played | Known | Sum | Mean | Median | Q1 | Q3 | YoY | 3-season avg
  all seasons for the other filters, selected season highlighted

[ Home attendance by club ]                              #att-panel-clubs
  chart clubs: horizontal bars, mean home attendance of the top 15 clubs
  search box (client side)
  # | Club | Home matches | Known | Sum | Mean | Median | Min | Max | YoY
  home matches only (home_club_id), sorted by mean, top 100, Club → /druzyny/<id>

[ Attendance by city ]                                   #att-panel-cities
  source note: "City is taken from the match venue (clubs have no city in the archive). This shows where spectators attended."
  missing-city note: number of played matches (for the filters) without a venue city, excluded from the ranking
  names note: spellings differing only in case or spaces (Kielce / KIELCE) are one city; the most common spelling is shown
  chart cities: horizontal bars, total spectators of the top 15 cities
  City detail charts: select (top 15 cities, default the top one) drives three charts
    cityTrend         total spectators per season (columns)
    cityCompetitions  total spectators per competition (horizontal bars)
    cityVenues        total spectators per venue (horizontal bars)
  search box (client side) filters all tables below by city, club, competition, season or venue
  # | City | Matches | Known | Sum | Mean | Median | Mode | Max | Clubs | Competitions
  ranking by total spectators (known matches only), top 100 cities; Mode = most frequent spectator count
  City | Home club | Competition | Matches | Known | Sum | Mean | Max
  contributions: home club × competition rows behind the ranked cities, top 300 by sum, grouped by city rank; Home club → /druzyny/<id>
  Seasons in each city:      City | Season | Matches | Known | Sum | Mean | Median | Max (oldest season first)
  Competitions in each city: City | Competition | Matches | Known | Sum | Mean | Median | Max (highest sum first)
  Venues in each city:       City | Venue | Matches | Known | Sum | Mean | Max (highest sum first); Venue → /hale/<id>
  breakdown tables cover the ranked cities only, at most 600 rows each, grouped by city rank

[ Attendance records ]                                   #att-panel-records
  top 50 matches by spectators
  # | Date | Season | Competition | Home | Score | Away | Venue | Spectators | Details → /mecze/<id>

[ Opponents ]                                            #att-panel-opponents
  needs the Home club filter, otherwise only a note is shown
  chart opponents: horizontal bars, mean attendance of the top 15 opponents (only when rows exist)
  # | Opponent | Matches | Known | Mean | Max | Diff vs club mean | Coverage
  opponents of the selected home club ranked by mean attendance at its home matches (top 100)
  Diff = opponent mean − the club's overall home mean for the same filters

[ Calendar ]                                             #att-panel-calendar
  chart heatmap: weekday × kickoff hour (cell = mean + known n)
  charts months / weekdays / hours: column charts of the mean, one above each table
  tables: Month | Weekday | Kickoff hour | Weekend vs weekday | Phase
  each row: Played | Known | Mean | relative bar

[ Extended records ]                                     #att-panel-extended
  Season records       max match per season (season filter ignored)
  Club home records    max per home club, top 30
  Venue records        max per venue, top 30
  Finals-like matches  phase ILIKE '%final%', top 30
  Rivalry pairs        max per (home, away) pair, top 30
  same columns as the top-50 table, each with a link to /mecze/<id>

[ Data science ]                                         #att-panel-science
  sample notes (cap, small n, correlation ≠ causation)
  KPIs: sample size | mean | std deviation | CV | IQR anomalies | forecast MAE
  Distribution    chart histogram + table of 10 equal-width bins + p10 p25 p50 p75 p90 p95
  Anomalies       IQR rule, top 10 high / low with links to the match
  Weekday effect  chart weekdayEffect + table: mean and n per weekday, “small n” flag below 5 matches
  Opponent effect (home club filter only) opponent mean − host mean, best and worst 10
  Result correlation  Pearson r: spectators vs goal difference and vs total goals
  Forecast        OLS, chronological 80/20 split, MAE/RMSE against a baseline
```

Rules:

- Played matches only (`PLAYED_SQL`). `spectators IS NULL` is missing and never counts as 0; `0` is a known closed-doors value, dropped only by Exclude zeros.
- Club metrics use home attendance only: the Home club filter means `home_club_id`.
- No venue capacity in the database, so there is no fill rate; coverage = known / played.
- Mean YoY compares the selected season (or the latest season with data) with the previous season; hidden when a date range is set.
- City name normalisation: the key is the venue city trimmed, with runs of whitespace collapsed to one space, and case-folded (`normalize_city_key` in `attendance_city_names.py`; in SQL `CITY_KEY_SQL = NULLIF(lower(regexp_replace(btrim(v.city), '\s+', ' ', 'g')), '')`). All city queries group by that key, so `Kielce` and `KIELCE` are one city. The display name is the most common original spelling (`MODE() WITHIN GROUP (ORDER BY ...)` over the trimmed, space-collapsed spelling). Breakdown rows are matched to the ranked city by the key and shown under its display name.
- City metrics: matches, known, sum, mean (`AVG`), median (`percentile_cont(0.5)`), mode of spectators (`MODE() WITHIN GROUP (ORDER BY m.spectators)`), max, distinct home clubs and competitions; all over matches with known attendance.
- City breakdowns (seasons, competitions, venues) are three extra queries restricted by a `ranked` CTE (the same top-N cities as the ranking), executed with the ranking, the contributions and the missing-city count over one connection by `fetch_city_bundle`, which returns a `CityBundle`. Venues are grouped by `v.id` (name, known matches, mean, sum, max).
- City is the venue city of the match: `LEFT JOIN ehf.venue v ON v.id = m.venue_id`. `ehf.club` and `club_edition` have no city. The ranking shows where spectators attended, not where a club is based. Matches without a venue city are excluded from the ranking and counted in a separate note. All other filters, `PLAYED_SQL` and the known-spectators predicate apply unchanged.
- Read-only: no writes and no migrations.

## Charts payload

`attendance_charts_payload(report)` (`attendance_analytics_chart.py`) builds one JSON object, rendered as `<script type="application/json" id="attendance-charts-data">` and read by `attendance_analytics.js`. Keys: `trend.points`, `heatmap`, `histogram` (`label`, `count`, `share`), `clubs` (top 15: `name`, `mean`, `known`), `months` / `weekdays` / `hours` (`label`, `mean`, `known`, `played`), `cities` (top 15: `name`, `total`, `mean`, `median`, `mode`, `known`), `cityDetails` (same top 15 cities: `name`, `seasons` [`season`, `total`, `mean`, `median`, `known`, `played`], `competitions` and `venues` [`name`, `total`, `mean`, `known`]), `opponents` (`name`, `mean`, `difference`; empty without a home club), `coverage` (`season`, `known`, `played`, `coverage` in %), `weekdayEffect` (`label`, `mean`, `n`).

Chart hosts are `div.att-chart[data-chart="trend|coverage|clubs|cities|heatmap|months|weekdays|hours|opponents|histogram|weekdayEffect"]`. Each is drawn by a renderer registered under the same name, so a new chart is a new renderer and a new key, not a change to existing ones.

## Stage 2 details

- Opponents: one aggregation over `away_club_id` (`played`, `known`, `AVG`, `MAX`), `NULL` spectators excluded from the mean through the known predicate.
- Calendar: one query (a CTE with the filtered matches and `UNION ALL` per dimension) using `KICKOFF_AT_SQL` for the date parts. Weekday is 0 = Mon … 6 = Sun (ISO weekday − 1), weekend = Sat–Sun. Matches without a kickoff time are skipped for month, weekday, hour and heatmap but kept in phase.
- Extended records: `DISTINCT ON` queries, executed over one connection; all other filters apply (season records ignore only the season filter).

## Stage 3 details

- The reader returns up to 8 000 matches with known attendance for the filters, the most recent ones when more exist (a note says so), sorted by kickoff in Python. Statistics are computed in the domain (`AttendanceScienceCalculator`), not in SQL.
- Stability uses the sample standard deviation (n − 1); CV = stdev / mean; below 5 matches a warning is shown.
- Anomalies: values outside Q1 − 1.5·IQR and Q3 + 1.5·IQR; needs at least 4 matches.
- Correlation is an association only. Scores are not known before the match, so they are never used for prediction. A warning appears below 30 matches.
- Forecast (`attendance_forecast.py`): OLS on standardized features known at kickoff — home club mean of strictly earlier matches (global mean of earlier matches for a club without history), weekend flag, month (sine/cosine) and kickoff hour. The first matches without any earlier data are dropped. Rows are split chronologically: the earliest 80% train, the latest 20% test. MAE/RMSE are compared with a baseline that predicts the home club mean of earlier matches. Fewer than 40 usable rows → forecast skipped with a warning.
