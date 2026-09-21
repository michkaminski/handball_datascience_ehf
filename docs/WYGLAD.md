# Wygląd strony

Skin jest skopiowany z panelu ZPRP (`admin.css`). Listy z menu Dane mają szkic tekstowy w `docs/strony/`. Zmianę strony zacznij od szkicu, potem wzorzec i pola `Strona` w `ehf/interface/pages.py`.

## Wzorce (`wzor`)

| Wzor | Szablon | Kiedy |
|---|---|---|
| `start` | `pages/start.html` | pulpit: filtry + pusta tabela + link do meczów |
| `lista` | `pages/lista.html` | katalog: filtry + nagłówki kolumn + pusty wiersz |
| `szczegoly` | `pages/szczegoly.html` | karta jednego obiektu (`/…/<id>`) |
| `narzedzie` | `pages/narzedzie.html` | import, eksport, walidacja — panel bez tabeli |

Nowy wygląd = nowy plik w `pages/` i nowy wiersz w tej tabeli. Istniejących szablonów ZPRP nie rozgałęziaj `if`-ami.

## Jak zdefiniować stronę

W `pages.py` dodajesz `Strona(...)`:

| Pole | Co wpisać |
|---|---|
| `klucz` | ten sam co pozycja w menu (`sezony`, `mecze`, …) |
| `endpoint` | nazwa trasy Flask, np. `lista_sezonow` |
| `sciezka` | URL, np. `/sezony` albo `/mecze/<int:identyfikator>` |
| `tytul` | `h1` |
| `okruszek` | `Start › Dane › …` |
| `opis` | jedno zdanie pod tytułem |
| `wzor` | `start` / `lista` / `szczegoly` / `narzedzie` |
| `filtry` | etykiety pól, puste = brak panelu filtrów |
| `kolumny` | nagłówki tabeli (dla `lista` i `start`) |
| `w_menu` | `False` dla kart szczegółów |

Menu górne i sidebar są w `navigation.py`. Link musi wskazywać `panel.<endpoint>`.

## Klasy CSS (z ZPRP)

Używaj tych samych nazw, bez wymyślania nowych na start:

- chrome: `header`, `brand`, `nav`, `sidebar`, `layout`, `footer`
- treść: `pagehead`, `crumb`, `panel`, `panel-body`, `filters`, `toolbar`, `table-wrap`, `note`
- akcje: `btn`, `btn secondary`, `btn small`

Szczegóły skina: `ehf/interface/static/css/admin.css`.
