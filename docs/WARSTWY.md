# Warstwy Handball EHF

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
