# Rozgrywki

| | |
|---|---|
| URL | `/rozgrywki` |
| View | `CompetitionListView` (`pages/competitions.html`) |
| Menu | Dane › Rozgrywki |
| Kod | `ehf/interface/competition_views.py` |
| Baza | `ehf.competition`, `ehf.competition_edition` |

Zmianę strony zacznij tutaj. Potem zsynchronizuj `filtry` / `kolumny` / `opis` w `pages.py`.

Wiersz to jedna edycja: `ehf.competition_edition`. Drużyny = różne `ehf.club_edition.club_id` tej edycji. Mecze = wszystkie mecze edycji.

```
Start › Dane › Rozgrywki
Rozgrywki
Ligi i puchary EHF w wybranym zakresie.

[ Filtry ]
  Szukaj: [tekst]   Sezon: [select]
  [Filtruj]  [Wyczyść]

[ Tabela ]
  ID | Sezon | Rozgrywki | Płeć | Drużyny | Mecze | Akcje
  kliknięcie nagłówka sortuje wszystkie pasujące edycje
  ID = competition_edition.id
  Płeć: Mężczyźni / Kobiety

  Akcje: Mecze → /mecze?season_id=&competition_id=
```
