# Mathematics library — article

Route `GET /matematyka/<category>/<slug>/`, endpoint `panel.math_article`, view `MathArticleView` ([mathematics_views.py](../../mathematics_views.py)). Unknown concept, alias, wrong section or missing file → 404. The content comes from `mathlib/content/articles/<category>/<slug>.html` and is processed by `mathlib.render.ArticleRenderer`: `data-concept` links get an `href` from the registry, `li[data-bib]` and `cite[data-bib]` get their description from `bibliography.json`, `h2` sections get a number and an anchor. A concept alias (e.g. `z-score`) has no page of its own; it leads to an anchor of the target article.

The article body is shared with the national app and is in Polish; the page chrome is English and a note says so (`<article lang="pl">`).

Anchors are a contract: every article has 13 sections with fixed `id`s (`intuicja` … `bibliografia`) and the main formula `id="eq-<slug>"`. The MAF dashboard links to them through concept identifiers (`links.concepts[*].anchors`: `definition` → `#definicja`, `formula` → `#wzor`, `derivation` → `#wyprowadzenie`, `example` → `#przyklad`).

Data: `page` (`ArticlePage`: `.article` {`concept`, `html`, `toc` [`id`, `title`, `level`, `number`]}, `.category`, `.previous`, `.next`, `.related`, `.used_by`), `categories`, `registry`.

## Text layout and change map

```text
Mathematics › Rozkłady › Rozkład beta
Rozkład beta
[short definition]  Used by: [MAF]
Article content is in Polish (shared library with the national app).
┌ Contents ────┐ ┌ article.ml-article ─────────────────────────────┐
│ 1. Intuicja  │ │ 1. Intuicyjne wprowadzenie                       │
│ 2. Definicja │ │ 2. Definicja formalna  [ml-def box]              │
│ …            │ │ 5. Wzory   \[ … \]                          (1)  │
│ 13. Bibliogr.│ │ 8. Przykład [ml-plot chart + sliders]            │
└──────────────┘ │ 13. Bibliografia                                 │
                 └──────────────────────────────────────────────────┘
[← previous]                                        [next →]
Related concepts in the registry: …
```

| Element | Selector | Data / code |
| --- | --- | --- |
| Table of contents | `aside.ml-toc a[data-ml-toc]` | `article.toc` (h2 + h3), highlighting in `mathlib.js` |
| Body | `article[data-ml-article]` | `article.html` |
| Formula numbers | `.ml-eq > .ml-eqnum` | `numberEquations()`; references `a.ml-eqref` |
| Charts | `.ml-plot[data-plot][data-params]` | types in `PLOT_TYPES` (`mathlib.js`); type and parameter names are the shared content contract, listed in `mathlib/AUTHORING.md` |
| Pager | `nav.ml-pager` | `page.previous`, `page.next` |
| Related | `ul.ml-related` | `page.related` (registry field `related`) |
