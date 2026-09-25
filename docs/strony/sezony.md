# Sezony

| | |
|---|---|
| URL | `/sezony` |
| View | `SeasonListView` (`pages/seasons.html`) |
| Menu | Dane › Sezony |
| Kod | `ehf/interface/season_views.py` |
| Baza | `ehf.season`, `ehf.competition_edition`, `ehf.match` |

Zmianę strony zacznij tutaj. Potem zsynchronizuj `filtry` / `kolumny` / `opis` w `pages.py`.

Stan archiwum:

| Stan | Kiedy |
|---|---|
| Pusty | brak edycji rozgrywek albo brak meczów |
| W toku | jest mecz `scheduled_or_no_result` |
| Kompletny | są mecze i żaden nie czeka na wynik |

```
Start › Dane › Sezony
Sezony
Przegląd sezonów i kompletności archiwum rozgrywek.

[ Filtry ]
  Szukaj: [tekst]   Stan: [select]
  [Filtruj]  [Wyczyść]

[ Tabela ]
  ID | Sezon | Rok rozpoczęcia | Rozgrywki | Mecze | Stan | Akcje
  kliknięcie nagłówka sortuje wszystkie pasujące sezony
  Rozgrywki = liczba ehf.competition_edition
  Mecze = wszystkie mecze sezonu

  Akcje: Rozgrywki → /rozgrywki?season_id=
          Mecze → /mecze?season_id=
```
