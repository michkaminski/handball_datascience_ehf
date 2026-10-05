# Strony

Te same pozycje co w panelu ZPRP. Tu tylko szkielet — inna baza dojdzie później.

Źródło prawdy UI: `ehf/interface/pages.py`.  
Źródło prawdy tabel: [BAZA.md](BAZA.md) (`../imports/sql/001_ehf_schema.sql`).

## Górny pasek

| Menu | URL | Wzor |
|---|---|---|
| Start | `/` | start |
| Dane | `/mecze` | lista |
| Reports | `/protokol` | narzedzie |
| Import | `/import` | narzedzie |
| Kontrola danych | `/kontrola` | narzedzie |
| Logi | `/logi` | lista |

## Dane

Szkic tekstowy każdej listy: `docs/strony/`. Zmianę strony zacznij od szkicu, potem `pages.py`.

| Menu | URL | Wzor | Szkic |
|---|---|---|---|
| Sezony | `/sezony` | season list (live) | [sezony.md](strony/sezony.md) |
| Rozgrywki | `/rozgrywki` | competition list (live) | [rozgrywki.md](strony/rozgrywki.md) |
| Drużyny | `/druzyny` | team list (live) | [druzyny.md](strony/druzyny.md) |
| Players | `/zawodnicy` | player list (live) | [zawodnicy.md](strony/zawodnicy.md) |
| Składy | `/sklady` | lista | [sklady.md](strony/sklady.md) |
| Matches | `/mecze` | match list (live) | [mecze.md](strony/mecze.md) |
| Tabele | `/tabele` | lista | [tabele.md](strony/tabele.md) |
| Scorers | `/strzelcy` | scorer list (live) | [strzelcy.md](strony/strzelcy.md) |
| Venues | `/hale` | venue list (live) | [hale.md](strony/hale.md) |
| Referees | `/sedziowie` | referee list (live) | [sedziowie.md](strony/sedziowie.md) |

## Reports

| Menu | URL | Wzor | Szkic |
|---|---|---|---|
| Match sheet | `/protokol` | A4 print (live) | [protokol.md](strony/protokol.md) |

## Karty (bez pozycji w menu)

| Strona | URL | Szkic |
|---|---|---|
| Match details | `/mecze/<id>` | [mecz.md](strony/mecz.md) |
| Player details | `/zawodnicy/<id>` | [zawodnik.md](strony/zawodnik.md) |
| Team details | `/druzyny/<id>` | [druzyna.md](strony/druzyna.md) |
| Venue details | `/hale/<id>` | [hala.md](strony/hala.md) |
| Referee details | `/sedziowie/<id>` | [sedzia.md](strony/sedzia.md) |

Linki do kart (`partials/detail_links.html`, `static/js/matches.js`): klik → modal, dwuklik → nowa karta, Ctrl/środkowy klik → domyślnie przeglądarka.

## Import i narzędzia

| Menu | URL | Wzor |
|---|---|---|
| Import danych | `/import` | narzedzie |
| Historia importów | `/historia-importow` | lista |
| Eksport danych | `/eksport` | narzedzie |
| Anomalie danych | `/anomalie` | lista |
| Walidacja danych | `/walidacja` | narzedzie |
| Logi aplikacji | `/logi` | lista |
