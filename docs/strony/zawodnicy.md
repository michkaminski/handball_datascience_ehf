# Zawodnicy

| | |
|---|---|
| URL | `/zawodnicy` |
| Wzor | `lista` |
| Menu | Dane › Zawodnicy |
| Kod | `ehf/interface/pages.py` → `klucz="zawodnicy"` |
| Karta | `/zawodnicy/<id>` |
| Baza | `ehf.person`, `ehf.player_edition` |

Zmianę strony zacznij tutaj. Potem zsynchronizuj `filtry` / `kolumny` / `opis` w `pages.py`.

```
Start › Dane › Zawodnicy
Zawodnicy
Zawodnicy i statystyki w wybranym zakresie.

[ Filtry ]
  Sezon: [____]  Rozgrywki: [____]  Drużyna: [____]
  Pozycja: [____]  Rocznik: [____]  Szukaj: [____]
  [Filtruj]  [Wyczyść]

[ Tabela ]
  ID | Imię | Nazwisko | Poz. | Drużyny | Rocznik | Wzrost | Waga | Akcje
  ---+------+----------+------+---------+---------+--------+------+------
  (pusto: szkielet — baza EHF osobna)

  Akcje wiersza (docelowo): Szczegóły → /zawodnicy/<id>
```
