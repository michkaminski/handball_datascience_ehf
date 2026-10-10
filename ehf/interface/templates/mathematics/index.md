# Mathematics library — home page

Route `GET /matematyka/`, endpoint `panel.math_index`, view `MathIndexView` ([mathematics_views.py](../../mathematics_views.py)). Menu item "Mathematics" in the top bar and "Mathematics library" in the sidebar.

Shows every section of the registry (`content/registry.json` of the `mathlib` package), its articles with a short definition, a client-side search box and the list of planned sport models (no links — not implemented). A note says that article content is in Polish (shared library with the national app).

Data: `categories` (tuple of `MathCategory`), `planned` (list of dicts `name`/`category`, `registry.planned_models`), `registry` (`MathRegistry`: `url(id)`, `version`, `concepts`, `bibliography`).

## Text layout and change map

```text
Start › Mathematics
Mathematics library
[description]
Article content is in Polish (shared library with the national app).
┌ Search concept [_______________] ┐
┌ 1. Podstawy statystyki ┐ ┌ 2. Rachunek prawd. ┐ ┌ 3. Rozkłady … ┐
│ Średnia arytmetyczna   │ │ …                  │ │ …             │
│   short definition     │ │                    │ │               │
└────────────────────────┘ └────────────────────┘ └───────────────┘
… 10. Modele sportowe: MAF + "Planned models"
Concept registry version … · N concepts · M verified sources
```

| Element | Selector | Data |
| --- | --- | --- |
| Search | `input[data-ml-search]` | filters `[data-ml-item]` and hides empty `[data-ml-category]` (`mathlib.js`) |
| Section card | `section.ml-card[data-ml-category]` | `item.category`, `item.articles` |
| Planned models | `ul.ml-planned` | `planned` (`registry.planned_models`) |
| Footer line | `p.note` | `registry.version`, `registry.concepts`, `registry.bibliography` |
