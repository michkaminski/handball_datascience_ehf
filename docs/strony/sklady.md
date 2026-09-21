# Składy

| | |
|---|---|
| URL | `/sklady` |
| Wzor | `lista` |
| Menu | Dane › Składy |
| Kod | `ehf/interface/pages.py` → `klucz="sklady"` |
| Baza | `ehf.match_lineup`, `ehf.player_edition` |

W ZPRP nie ma jeszcze widoku. Szkic jest propozycją EHF.

Zmianę strony zacznij tutaj. Potem zsynchronizuj `filtry` / `kolumny` / `opis` w `pages.py`.

```
Start › Dane › Składy
Składy
Składy meczowe i sezonowe.

[ Filtry ]
  Sezon: [____________]   Drużyna: [____________]   Szukaj: [____________]
  [Filtruj]  [Wyczyść]

[ Tabela ]
  ID | Sezon | Drużyna | Zawodnik | Pozycja | Nr | Akcje
  ---+-------+---------+----------+---------+----+------
  (pusto: szkielet — baza EHF osobna)

  Akcje wiersza (docelowo): Zawodnik, Mecz
```
