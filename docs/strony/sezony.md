# Sezony

| | |
|---|---|
| URL | `/sezony` |
| Wzor | `lista` |
| Menu | Dane › Sezony |
| Kod | `ehf/interface/pages.py` → `klucz="sezony"` |
| Baza | `ehf.season` |

Zmianę strony zacznij tutaj. Potem zsynchronizuj `filtry` / `kolumny` / `opis` w `pages.py`.

```
Start › Dane › Sezony
Sezony
Przegląd sezonów i kompletności archiwum rozgrywek.

[ Filtry ]
  Szukaj: [____________]   Stan: [____________]
  [Filtruj]  [Wyczyść]

[ Tabela ]
  ID | Sezon | Rok rozpoczęcia | Rozgrywki | Mecze | Stan | Akcje
  ---+-------+-----------------+-----------+-------+------+------
  (pusto: szkielet — baza EHF osobna)

  Akcje wiersza (docelowo): Rozgrywki, Mecze
```
