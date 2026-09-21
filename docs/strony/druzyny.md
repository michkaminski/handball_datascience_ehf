# Drużyny

| | |
|---|---|
| URL | `/druzyny` |
| Wzor | `lista` |
| Menu | Dane › Drużyny |
| Kod | `ehf/interface/pages.py` → `klucz="druzyny"` |
| Baza | `ehf.club`, `ehf.club_edition` |

Zmianę strony zacznij tutaj. Potem zsynchronizuj `filtry` / `kolumny` / `opis` w `pages.py`.

```
Start › Dane › Drużyny
Drużyny
Kluby i ekipy w sezonach EHF.

[ Filtry ]
  Szukaj: [____________]   Sezon: [____________]   Płeć: [____________]
  [Filtruj]  [Wyczyść]

[ Tabela ]
  ID | Sezon | Drużyna | Płeć | Miasto | Mecze | Status | Akcje
  ---+-------+---------+------+--------+-------+--------+------
  (pusto: szkielet — baza EHF osobna)

  Akcje wiersza (docelowo): Mecze, Zawodnicy
```
