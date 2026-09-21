# Hale

| | |
|---|---|
| URL | `/hale` |
| Wzor | `lista` |
| Menu | Dane › Hale |
| Kod | `ehf/interface/pages.py` → `klucz="hale"` |
| Karta | `/hale/<id>` |
| Baza | `ehf.venue` |

Zmianę strony zacznij tutaj. Potem zsynchronizuj `filtry` / `kolumny` / `opis` w `pages.py`.

```
Start › Dane › Hale
Hale
Hale i areny meczów EHF.

[ Filtry ]
  Szukaj: [____________]   Miasto: [____________]
  [Filtruj]  [Wyczyść]

[ Tabela ]
  ID | Nazwa | Miasto | Adres | Pojemność | Mecze | Akcje
  ---+-------+--------+-------+-----------+-------+------
  (pusto: szkielet — baza EHF osobna)

  Akcje wiersza (docelowo): Szczegóły → /hale/<id>
```
