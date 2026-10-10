# Mathematics library layout

Shared layout of the `/matematyka/…` pages (`_layout.html`). Extends `base.html` (top bar, panel sidebar, footer) and adds its own section navigation and assets: KaTeX (local, `static/vendor/katex`, MIT licence), `css/mathlib.css`, `js/mathlib.js`. ECharts is loaded lazily from `data-echarts-url`, only on pages with an `ml-plot` chart.

Overrides `{% block tytul %}` (the `base.html` default uses an undefined `strona`), fills `{% block tresc %}` and loads the scripts in `{% block scripts %}`.

Data: `categories` (`MathCategory` from `MathLibraryService.categories()`: `.category` {`id`, `name`, `description`}, `.articles` [`Concept`]), `registry` (`MathRegistry` — `registry.url(id)` builds addresses from the concept registry), optionally `active_category` and `active_article`, set by the child template.

Child block: `{% block mathematics %}`.

## Text layout and change map

```text
┌ base.html: header / nav (Mathematics active) / sidebar ───────────────────────┐
│ ┌ nav.ml-sidenav ───────┐ ┌ div.ml-main ─────────────────────────────────────┐ │
│ │ ∑ Mathematics library │ │ {% block mathematics %}                          │ │
│ │ ▸ Podstawy statystyki │ │                                                  │ │
│ │   – Średnia …         │ │                                                  │ │
│ │ ▸ Rachunek prawd. …   │ │                                                  │ │
│ └───────────────────────┘ └──────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────┘
```

Section and article names come from the shared registry and stay in Polish.

| Element | File / selector | Data |
| --- | --- | --- |
| Container | `div.ml-shell[data-mathlib][data-echarts-url]` | ECharts URL |
| Section navigation | `nav.ml-sidenav details/summary` | `categories`, `active_category`, `active_article` |
| Style | `static/css/mathlib.css` (`.ml-*`) | — |
| Formulas, charts, table of contents | `static/js/mathlib.js` | KaTeX auto-render, `.ml-eq` numbering, `.ml-plot` |
