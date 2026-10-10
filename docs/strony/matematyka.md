# Mathematics

| | |
|---|---|
| URL | `/matematyka/`, `/matematyka/<category>/`, `/matematyka/<category>/<slug>/` |
| View | `MathIndexView`, `MathCategoryView`, `MathArticleView` (`ehf/interface/mathematics_views.py`); templates `mathematics/_layout.html`, `index.html`, `category.html`, `article.html` (each with a companion `.md`) |
| Menu | top bar "Mathematics"; sidebar "Mathematics library" |
| Code | `ehf/services/mathematics.py` (`MathLibraryService`, `MathCategory`, `ArticlePage`); shared package `mathlib` (`registry.py`, `render.py`, `content/registry.json`, `content/bibliography.json`, `content/articles/<category>/<slug>.html`, `AUTHORING.md`) |
| Assets | `static/js/mathlib.js`, `static/css/mathlib.css` (`.ml-*`), `static/vendor/katex` (with `contrib/auto-render`), `static/vendor/echarts` (lazy) |
| Database | none |

```
Start › Mathematics
Mathematics library
Article content is in Polish (shared library with the national app).

┌ nav.ml-sidenav ──────┐ ┌ div.ml-main ───────────────────────────────────────┐
│ ∑ Mathematics library│ │ /matematyka/                                       │
│ ▸ section (n)        │ │   Search concept [____]  (client side)             │
│   – article          │ │   section cards: articles + short definitions      │
│ ▸ section (n)        │ │   Modele sportowe: MAF + Planned models            │
│   …                  │ │   Concept registry version … · N concepts · M src  │
└──────────────────────┘ │                                                    │
                         │ /matematyka/<category>/                            │
                         │   article link cards [MAF tag]; empty → note       │
                         │                                                    │
                         │ /matematyka/<category>/<slug>/                     │
                         │   Contents (sticky) | article body (KaTeX, plots)  │
                         │   [← previous]  [next →]  Related concepts         │
                         └────────────────────────────────────────────────────┘
```

Rules:

- Content (section names, article names and bodies) is the shared Polish library; only the page chrome is English.
- Unknown section, unknown concept, alias or a concept outside the section → 404.
- Section anchors (`definicja`, `wzor`, `wyprowadzenie`, `przyklad`, …) and `eq-<slug>` are a contract used by the MAF tab (`links.concepts[*].anchors`).
- `.ml-plot[data-plot][data-params]` charts: plot type names (`normal`, `beta`, `beta-mean`, `binomial`, `betabinomial`, `negbinomial`, `logistic`, `beta-update`, `shrinkage`) and parameter names are part of the shared content contract and must not be renamed.
- Every template override sets `{% block tytul %}` (the `base.html` default uses an undefined `strona`).
- Read-only: no database access.
