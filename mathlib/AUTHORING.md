# Biblioteka Matematyka — zasady pisania artykułów

Pakiet `mathlib` jest wspólnym źródłem treści działu `/matematyka/` dla aplikacji `handball_datascience` i `handball_datascience_ehf`. Obie aplikacje mają identyczną kopię katalogu `content/` oraz modułów Pythona; zmianę wprowadza się w obu repozytoriach naraz (test `test_mathlib_*` porównuje sumę kontrolną treści z `content/CHECKSUM`).

## Pliki

| Plik | Rola |
| --- | --- |
| `content/registry.json` | Centralny rejestr pojęć: identyfikator, nazwa, krótka definicja, dział, artykuł, kotwica, powiązania, modele, bibliografia |
| `content/bibliography.json` | Zweryfikowane źródła (DOI sprawdzone w Crossref, URL sprawdzone HTTP). Nowe źródło dopisujemy dopiero po weryfikacji |
| `content/articles/<dzial>/<slug>.html` | Treść artykułu: fragment HTML z LaTeX-em, bez `<html>`, `<head>`, `<body>` |

Adres artykułu: `/matematyka/<dzial>/<slug>/`. Kod aplikacji odwołuje się do pojęć wyłącznie przez identyfikator z rejestru (`concept_url("rozklad-beta", "wzor")`), nigdy przez wpisany ręcznie URL.

## Struktura artykułu

Artykuł ma dokładnie 13 sekcji, w tej kolejności i z tymi identyfikatorami (kotwice są częścią kontraktu — testy je sprawdzają):

```html
<section id="intuicja"><h2>Intuicyjne wprowadzenie</h2> … </section>
<section id="definicja"><h2>Definicja formalna</h2> … </section>
<section id="symbole"><h2>Wykaz symboli</h2> <table class="ml-symbols">…</table> </section>
<section id="zalozenia"><h2>Założenia</h2> … </section>
<section id="wzory"><h2>Wzory</h2> … </section>
<section id="twierdzenia"><h2>Twierdzenia</h2> … </section>
<section id="wyprowadzenie"><h2>Dowody i wyprowadzenia</h2> … </section>
<section id="przyklad"><h2>Przykład liczbowy krok po kroku</h2> … </section>
<section id="interpretacja"><h2>Interpretacja wyniku</h2> … </section>
<section id="pilka-reczna"><h2>Zastosowanie w piłce ręcznej</h2> … </section>
<section id="ograniczenia"><h2>Ograniczenia metody</h2> … </section>
<section id="powiazane"><h2>Powiązane zagadnienia</h2> … </section>
<section id="bibliografia"><h2>Bibliografia</h2> … </section>
```

Numer sekcji i spis treści dodaje szablon — nie wpisuj numerów w `<h2>`. Podsekcje: `<h3 id="…">`. Identyfikatory w obrębie artykułu są unikalne, małe litery, cyfry i myślniki.

Gdy sekcja nie ma zastosowania (np. brak twierdzeń), zostaw ją z jednym akapitem wyjaśniającym dlaczego i odsyłaczem do miejsca, gdzie temat jest rozwinięty.

## Elementy

| Element | Zapis |
| --- | --- |
| Wzór w tekście | `\( … \)` |
| Wzór numerowany | `<div class="ml-eq" id="eq-<slug>-<nazwa>">\[ … \]</div>` — numeruje szablon |
| Główny wzór pojęcia | musi mieć `id="eq-<slug>"` (kotwica `wzor` w rejestrze) |
| Odwołanie do wzoru | `<a class="ml-eqref" href="#eq-…"></a>` — tekst „(n)” wstawia skrypt |
| Definicja | `<div class="ml-box ml-def" id="def-<nazwa>"><p class="ml-box-title">Definicja</p> … </div>` |
| Twierdzenie | `<div class="ml-box ml-thm" id="thm-<nazwa>"><p class="ml-box-title">Twierdzenie (nazwa)</p> … </div>` |
| Dowód | `<div class="ml-proof"><p class="ml-box-title">Dowód</p> … <p class="ml-qed">∎</p></div>` |
| Uwaga | `<div class="ml-box ml-note"> … </div>` |
| Przykład krok po kroku | `<ol class="ml-steps"><li>…</li></ol>` |
| Tabela danych | `<table class="ml-table">` z `<thead>` |
| Link do pojęcia | `<a data-concept="rozklad-beta">rozkład beta</a>`, opcjonalnie `data-anchor="wzory"` — `href` uzupełnia serwer na podstawie rejestru |
| Bibliografia | `<ul class="ml-bib"><li data-bib="gelman2013bda"></li></ul>` — opis wstawia serwer z `bibliography.json`; wolno używać wyłącznie istniejących kluczy |
| Cytowanie w tekście | `<cite data-bib="ferrari2004"></cite>` — serwer wstawia „(Ferrari i Cribari-Neto, 2004)” |
| Wykres interaktywny | `<div class="ml-plot" data-plot="<typ>" data-params='{"a": 2, "b": 5}'></div>` |

Typy wykresów (`data-plot`) i ich parametry:

| Typ | Parametry | Rysuje |
| --- | --- | --- |
| `normal` | `mu`, `sigma` | gęstość N(μ, σ) |
| `beta` | `a`, `b` | gęstość Beta(a, b) |
| `beta-mean` | `mu`, `phi` | gęstość Beta w parametryzacji średnia–precyzja |
| `binomial` | `n`, `p` | rozkład Bin(n, p) |
| `betabinomial` | `n`, `a`, `b` | rozkład BetaBin(n, a, b) |
| `negbinomial` | `mu`, `kappa` | rozkład NB(μ, κ) |
| `logistic` | `alpha`, `beta` | krzywa \( \operatorname{logit}^{-1}(\alpha + \beta x) \) |
| `beta-update` | `a`, `b`, `k`, `n` | prior Beta(a, b) i posterior po k sukcesach w n próbach |
| `shrinkage` | `tau`, `sigma` | ściąganie średnich grup do średniej ogólnej w zależności od liczby meczów |

Każdy wykres dostaje suwaki parametrów. Pod wykresem dopisz zdanie, co czytelnik ma zauważyć.

## Język i poziom

- Polski, styl podręcznika akademickiego; definicje i twierdzenia ścisłe, z założeniami.
- Liczby w przykładach pokazuj krok po kroku, z zaokrągleniami podanymi jawnie. Dane wymyślone oznacz jako „dane ilustracyjne”.
- Sekcja „Zastosowanie w piłce ręcznej” opisuje, gdzie pojęcie pracuje w MAF lub innych raportach, z linkiem `data-concept="atrakcyjnosc-frekwencyjna"` tam, gdzie to zasadne.
- Nie wymyślaj źródeł. Gdy potrzebne źródło nie istnieje w `bibliography.json`, zgłoś je do weryfikacji zamiast dopisywać.
