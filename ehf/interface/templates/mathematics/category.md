# Mathematics library — section

Route `GET /matematyka/<category>/`, endpoint `panel.math_category`, view `MathCategoryView` ([mathematics_views.py](../../mathematics_views.py)). Unknown section → 404. A section without articles (e.g. "Wnioskowanie statystyczne") shows an in-preparation note with links to Bayesian statistics and Model validation.

Data: `result` (`MathCategory`: `.category`, `.articles`), `categories` (side navigation), `planned` (planned models of this section only), `registry`.

## Text layout and change map

```text
Mathematics › Statystyka bayesowska
Statystyka bayesowska
[section description]
┌ Twierdzenie Bayesa w estymacji ┐ ┌ Priory ┐ ┌ … ┐   (link cards)
│ short definition   [MAF]       │
[Planned models]  (Modele sportowe only)
```

| Element | Selector | Data |
| --- | --- | --- |
| Article card | `a.ml-card-link` | `result.articles`, `registry.url(id)`, `models` |
| Empty section | `.ml-empty` | — |
| Planned | `ul.ml-planned` | `planned` |
