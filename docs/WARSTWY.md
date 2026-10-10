# Warstwy — Europejskie puchary oczami danych

Jedna aplikacja Flask, cztery warstwy. Importer w `../imports` nie należy do tej apki.

| Warstwa | Katalog | Wolno | Nie wolno |
|---|---|---|---|
| interface | `ehf/interface/` | trasy, HTML, CSS, menu | SQL, reguły biznesowe |
| services | `ehf/services/` | przypadki użycia | Flask, SQL |
| domain | `ehf/domain/` | mecz, klub, sezon | Flask, SQL, HTML |
| infrastructure | `ehf/infrastructure/` | odczyt schematu `ehf` | szablony |

Baza: schemat z `../imports/sql/001_ehf_schema.sql` — mapowanie w [BAZA.md](BAZA.md).

Dziś działa tylko **interface** (szkielet stron). Kolejne warstwy dokładamy przy pierwszym odczycie z bazy.

Wejście: `app.py` → `create_app()`. Nowa strona-szkielet = rekord w `pages.py`. Lista meczów jest pierwszą stroną z warstwami (`MatchListService` + `PsycopgMatchListReader`).

W kodzie tej apki nazwy są po angielsku (`Match`, `Season`, `Venue`).

## Shared packages `maf` and `mathlib`

Two packages live next to `ehf/` and are identical copies of the ones in `handball_datascience/src/` (the national app). They do not depend on Flask, the database or `ehf`:

| Package | Role |
|---|---|
| `maf/` | Attendance Appeal Model (MAF): data quality, features, hierarchical Bayesian model, NUTS sampler, diagnostics, IAF, forecasts, chronological validation, artifact store |
| `mathlib/` | Mathematics library: concept registry, verified bibliography, articles (Polish), renderer, link/anchor validator |

Training runs outside HTTP requests: `python scripts/train_maf.py [men-count|women-count]` reads the database read-only and writes versioned artifacts to `var/maf/` (env `MAF_STORE`). The app reads only the artifacts (`AttendanceAppealService`). Engine strings that are Polish in the shared package are translated in `ehf/services/attendance_appeal_i18n.py`.

When changing either package, change both repositories; `mathlib/content/CHECKSUM` must match in both (test `test_math_library_is_valid_and_in_sync`). Full description of the model: `/matematyka/modele-sportowe/atrakcyjnosc-frekwencyjna/`; architecture: `handball_datascience/docs/MAF.md`.
