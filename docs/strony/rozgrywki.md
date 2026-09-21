# Rozgrywki

| | |
|---|---|
| URL | `/rozgrywki` |
| Wzor | `lista` |
| Menu | Dane › Rozgrywki |
| Kod | `ehf/interface/pages.py` → `klucz="rozgrywki"` |
| Baza | `ehf.competition`, `ehf.competition_edition` |

Zmianę strony zacznij tutaj. Potem zsynchronizuj `filtry` / `kolumny` / `opis` w `pages.py`.

```
Start › Dane › Rozgrywki
Rozgrywki
Ligi i puchary EHF w wybranym zakresie.

[ Filtry ]
  Szukaj: [____________]   Sezon: [____________]
  [Filtruj]  [Wyczyść]

[ Tabela ]
  ID | Sezon | Rozgrywki | Płeć | Drużyny | Mecze | Akcje
  ---+-------+-----------+------+---------+-------+------
  (pusto: szkielet — baza EHF osobna)

  Akcje wiersza (docelowo): Mecze
```
