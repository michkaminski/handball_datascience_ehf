# Strony

Te same pozycje co w panelu ZPRP. Tu tylko szkielet — inna baza dojdzie później.

Źródło prawdy UI: `ehf/interface/pages.py`.  
Źródło prawdy tabel: [BAZA.md](BAZA.md) (`../imports/sql/001_ehf_schema.sql`).

## Górny pasek

| Menu | URL | Wzor |
|---|---|---|
| Start | `/` | start |
| Dane | `/mecze` | lista |
| Import | `/import` | narzedzie |
| Kontrola danych | `/kontrola` | narzedzie |
| Logi | `/logi` | lista |

## Dane

Szkic tekstowy każdej listy: `docs/strony/`. Zmianę strony zacznij od szkicu, potem `pages.py`.

| Menu | URL | Wzor | Szkic |
|---|---|---|---|
| Sezony | `/sezony` | lista | [sezony.md](strony/sezony.md) |
| Rozgrywki | `/rozgrywki` | lista | [rozgrywki.md](strony/rozgrywki.md) |
| Drużyny | `/druzyny` | lista | [druzyny.md](strony/druzyny.md) |
| Zawodnicy | `/zawodnicy` | lista | [zawodnicy.md](strony/zawodnicy.md) |
| Składy | `/sklady` | lista | [sklady.md](strony/sklady.md) |
| Matches | `/mecze` | match list (live) | [mecze.md](strony/mecze.md) |
| Tabele | `/tabele` | lista | [tabele.md](strony/tabele.md) |
| Strzelcy | `/strzelcy` | lista | [strzelcy.md](strony/strzelcy.md) |
| Hale | `/hale` | lista | [hale.md](strony/hale.md) |
| Sędziowie | `/sedziowie` | lista | [sedziowie.md](strony/sedziowie.md) |

## Karty (bez pozycji w menu)

| Strona | URL |
|---|---|
| Szczegóły meczu | `/mecze/<id>` |
| Szczegóły zawodnika | `/zawodnicy/<id>` |
| Szczegóły hali | `/hale/<id>` |

## Import i narzędzia

| Menu | URL | Wzor |
|---|---|---|
| Import danych | `/import` | narzedzie |
| Historia importów | `/historia-importow` | lista |
| Eksport danych | `/eksport` | narzedzie |
| Anomalie danych | `/anomalie` | lista |
| Walidacja danych | `/walidacja` | narzedzie |
| Logi aplikacji | `/logi` | lista |
