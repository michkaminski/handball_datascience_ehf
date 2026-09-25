# Drużyny

| | |
|---|---|
| URL | `/druzyny` |
| View | `TeamListView` (`pages/teams.html`) |
| Menu | Dane › Drużyny |
| Kod | `ehf/interface/team_views.py` |
| Baza | `ehf.club`, `ehf.club_edition` |

Zmianę strony zacznij tutaj. Potem zsynchronizuj `filtry` / `kolumny` / `opis` w `pages.py`.

Wiersz to klub w sezonie (edycje zgrupowane po `club_id` i `season_id`). Miasto to najczęstsze miasto hali, w której klub był gospodarzem w tym sezonie. Status: Aktywna, gdy jest mecz; inaczej Bez meczów.

```
Start › Dane › Drużyny
Drużyny
Kluby i ekipy w sezonach EHF.

[ Filtry ]
  Szukaj: [tekst]   Sezon: [select]   Płeć: [select]
  [Filtruj]  [Wyczyść]

[ Tabela ]
  ID | Sezon | Drużyna | Płeć | Miasto | Mecze | Status | Akcje
  kliknięcie nagłówka sortuje wszystkie pasujące drużyny
  ID = ehf.club.id
  Płeć z ehf.competition.gender

  Akcje: Mecze → /mecze?season_id=&club=
          Zawodnicy → /zawodnicy?season_id=&club_id=
```
