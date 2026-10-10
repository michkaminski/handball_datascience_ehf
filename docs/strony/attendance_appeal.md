# Opponent appeal (MAF)

| | |
|---|---|
| URL | `/raporty/frekwencja?tab=maf` (tab of [Attendance](attendance_analytics.md)) |
| View | `AttendanceAnalyticsView` renders the tab (`partials/attendance_appeal_panel.html`, included from `pages/attendance_analytics.html`); JSON views in `ehf/interface/attendance_appeal_views.py` |
| Menu | Reports › Attendance › tab "Opponent appeal (MAF)" |
| Code | `ehf/domain/attendance_appeal.py` (`APPEAL_MODELS`, `METRIC_CONCEPTS`); `ehf/services/attendance_appeal.py` (`AttendanceAppealService`); `ehf/infrastructure/attendance_appeal_reader.py`; shared engine package `maf` (training, posterior, forecast, diagnostics); `scripts/train_maf.py` |
| Assets | `static/js/attendance_appeal.js`, `static/css/attendance_appeal.css` (`.maf-*`), `static/vendor/echarts`, `static/vendor/katex` |
| Data | trained model artifacts in `var/maf/<key>/…` (`MAF_STORE` overrides the path); training reads `ehf.match.spectators` and related tables once, the page does not query the database for MAF |

```
[ Opponent appeal (MAF) ]                                #att-panel-maf
  section#att-panel-maf[data-attendance-panel] > div.maf[data-maf][data-echarts-url][data-url-*]
  Opponent Attendance Appeal Model (MAF)       Model [Men — spectators ▾]  [Scientific documentation of the model]
  ! The report filters above do not narrow the model (estimated once on all matches of a gender)

  no trained model → "No MAF model has been trained yet" + `python scripts/train_maf.py`

  status bar     label · version · trained · matches · period · max R-hat (i) · min ESS (i)
  KPIs           Total | Mean | Median | Mean fill rate (n/a) | Matches | Highest | Largest opponent effect | Highest IAF
  sub-nav        Ranking | Forest plot | IAF trends | Posterior | Host analysis | Simulator | Deviations and records | Diagnostics | Data quality

  #maf-ranking      search | [x] reliable only | min. matches | [Compare selected (0/2)] [Export CSV]
                    # | ☐ | Club | Matches (away) | Mean | Median | Fill rate | IAF | Extra spectators | P(IAF > 100) | 95% interval | [How computed?]
                    click row → details (as opponent / as host / IAF by season); 50 rows + [Show more]
  #maf-forest       sort (index / narrowest / widest / matches) | clubs 20/30/50 | [x] reliable only → ECharts forest
  #maf-trends       add up to 6 clubs → seasonal IAF lines with 80% band + table
  #maf-posterior    club select → histogram of posterior IAF samples, P(IAF > 100)
  #maf-host         host select → expected attendance with a typical opponent; top / bottom opponents
  #maf-simulator    Host | Opponent | Competition | Season | Venue | Capacity (optional) | Weekday | Kickoff | Phase | Threshold
                    [Simulate] → expected, median, credible interval of the mean, predictive intervals, P(≥ threshold), histogram
  #maf-deviations   heatmap host × season (mean z) | positive / negative surprises | records season / club / venue
  #maf-diagnostics  MCMC convergence | chronological validation | coefficients | hierarchy | global parameters | PPC + PIT charts
  #maf-quality      input counts + example issues

  dialog.maf-dialog   "How was this computed?" — IAF formula (KaTeX), central-value illustration, posterior method, coefficients
  div.maf-popover     (i) icons → concept name, summary, links Definition / Formula / Derivation / Example / Full model documentation
```

JSON endpoints (all take `model=<key>`, default the first model):

| Endpoint | URL | Params | Returns |
|---|---|---|---|
| `panel.appeal_data` | `/raporty/frekwencja/maf/data` | `model` | panel payload: `model`, `quality`, `diagnostics`, `coefficients`, `kpi`, `clubs`, `hosts`, `competitions`, `venues`, `surprises`, `records`, `heatmap`, `ppc`, `backtest`, `links` |
| `panel.appeal_club` | `/raporty/frekwencja/maf/club/<club_id>` | `model` | `club` (with histogram and central values), `model`, `links` |
| `panel.appeal_host` | `/raporty/frekwencja/maf/host/<club_id>` | `model` | host-opponent analysis |
| `panel.appeal_compare` | `/raporty/frekwencja/maf/compare` | `a`, `b`, `model` | `p_first_greater`, `mcse`, `difference` |
| `panel.appeal_forecast` | `/raporty/frekwencja/maf/forecast` | `host`, `opponent`, `competition`, `season`, `capacity`, `weekday`, `hour`, `phase`, `threshold`, `model` | predictive distribution |
| `panel.appeal_export` | `/raporty/frekwencja/maf/export.csv` | `model` | CSV of the ranking (UTF-8 BOM) |

`links` = `concepts` (id → `name`, `summary`, `url`, `anchors` {`definition`, `formula`, `derivation`, `example`}), `metrics` (metric key → `concept`, `url`), `model` (URL of the MAF article). Metric keys (`iaf`, `rhat`, `srednia`, …) are shared with the national app.

Rules:

- The page filters never narrow the model. MAF is trained offline per gender by `python scripts/train_maf.py [key]`; the page only reads the latest artifact.
- EHF has no venue capacity, so both models (`men-count`, `women-count`) measure the number of spectators. Fill rate shows `n/a`; the simulator capacity is optional and only used for approximate fill rates and P(full house).
- Model status from the engine: `ok` / `ostrzezenie` / `niewiarygodny`, displayed as ok / warning / unreliable.
- Missing model → JSON 404 `{"error": "Model … has not been trained yet. Run: python scripts/train_maf.py …"}`; bad parameters → 400 `{"error": …}`.
- IAF = 100 is the average opponent (sum-to-zero constraint); results are posterior summaries (median, 95% credible interval, P(IAF > 100)), not point estimates.
- Charts (ECharts, SVG renderer) are drawn when the tab becomes visible; ECharts is loaded lazily from `data-echarts-url` on the `[data-maf]` element.
- Numbers and dates use the `en-GB` locale. Labels produced by the shared engine (coefficient names, notes, issue labels) may be in Polish.
- Read-only: no writes to the database.
