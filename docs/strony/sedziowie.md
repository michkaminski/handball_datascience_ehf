# Sędziowie

| | |
|---|---|
| URL | `/sedziowie` |
| Wzor | `lista` |
| Menu | Dane › Sędziowie |
| Kod | `ehf/interface/pages.py` → `klucz="sedziowie"` |
| Baza | `ehf.match_official` (`role = 'referee'`) |

Zmianę strony zacznij tutaj. Potem zsynchronizuj `filtry` / `kolumny` / `opis` w `pages.py`.

```
Start › Dane › Sędziowie
Sędziowie
Sędziowie spotkań EHF.

[ Filtry ]
  Szukaj: [____________]   Miasto: [____________]
  [Filtruj]  [Wyczyść]

[ Tabela ]
  ID | Nazwisko | Miasto | Mecze | Akcje
  ---+----------+--------+-------+------
  (pusto: szkielet — baza EHF osobna)

  Akcje wiersza (docelowo): Mecze
```
