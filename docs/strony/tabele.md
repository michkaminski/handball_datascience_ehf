# Tabele

| | |
|---|---|
| URL | `/tabele` |
| Wzor | `lista` |
| Menu | Dane › Tabele |
| Kod | `ehf/interface/pages.py` → `klucz="tabele"` |
| Baza | wyliczane z `ehf.match` (brak tabeli ligowej) |

W ZPRP nie ma jeszcze widoku. Szkic jest propozycją EHF.

Zmianę strony zacznij tutaj. Potem zsynchronizuj `filtry` / `kolumny` / `opis` w `pages.py`.

```
Start › Dane › Tabele
Tabele
Tabele grup i lig EHF.

[ Filtry ]
  Sezon: [____________]   Rozgrywki: [____________]
  [Filtruj]  [Wyczyść]

[ Tabela ]
  Poz. | Drużyna | M | Z | R | P | Bramki | Pkt
  -----+---------+---+---+---+---+--------+----
  (pusto: szkielet — baza EHF osobna)
```
