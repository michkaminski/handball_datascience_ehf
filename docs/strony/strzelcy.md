# Strzelcy

| | |
|---|---|
| URL | `/strzelcy` |
| Wzor | `lista` |
| Menu | Dane › Strzelcy |
| Kod | `ehf/interface/pages.py` → `klucz="strzelcy"` |
| Baza | `ehf.match_player_stat`, `ehf.match_lineup`, `ehf.person` |

W ZPRP nie ma jeszcze widoku. Szkic jest propozycją EHF.

Zmianę strony zacznij tutaj. Potem zsynchronizuj `filtry` / `kolumny` / `opis` w `pages.py`.

```
Start › Dane › Strzelcy
Strzelcy
Klasyfikacja strzelców.

[ Filtry ]
  Sezon: [____________]   Rozgrywki: [____________]
  [Filtruj]  [Wyczyść]

[ Tabela ]
  Poz. | Zawodnik | Drużyna | Bramki | Mecze
  -----+----------+---------+--------+------
  (pusto: szkielet — baza EHF osobna)

  Zawodnik (docelowo): link → /zawodnicy/<id>
```
