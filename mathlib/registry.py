from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from functools import cache
from html.parser import HTMLParser
from pathlib import Path

CONTENT_DIR = Path(__file__).resolve().parent / "content"


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    description: str
    order: int


@dataclass(frozen=True)
class Concept:
    id: str
    name: str
    category: str
    summary: str
    article: str
    anchor: str | None
    related: tuple[str, ...]
    models: tuple[str, ...]
    bibliography: tuple[str, ...]
    layout: str = "concept"

    @property
    def is_alias(self) -> bool:
        return self.article != self.id


@dataclass(frozen=True)
class BibEntry:
    key: str
    data: dict[str, str | int]

    def citation(self) -> str:
        authors = str(self.data.get("authors", ""))
        names = [part.split(",")[0].strip() for part in authors.split(";") if part.strip()]
        if len(names) > 2:
            label = f"{names[0]} i in."
        elif len(names) == 2:
            label = f"{names[0]} i {names[1]}"
        else:
            label = names[0] if names else ""
        return f"{label}, {self.data.get('year', '')}"

    def link(self) -> str | None:
        doi = self.data.get("doi")
        if doi:
            return f"https://doi.org/{doi}"
        url = self.data.get("url")
        return str(url) if url else None


class MathRegistry:
    def __init__(self, content_dir: Path = CONTENT_DIR) -> None:
        self.content_dir = content_dir
        raw = json.loads((content_dir / "registry.json").read_text(encoding="utf-8"))
        bibliography = json.loads((content_dir / "bibliography.json").read_text(encoding="utf-8"))
        self.version: str = raw["version"]
        self.base_path: str = raw["base_path"]
        self.sections: tuple[tuple[str, str], ...] = tuple(
            (item["id"], item["title"]) for item in raw["article_sections"]
        )
        self.model_sections: tuple[tuple[str, str], ...] = tuple(
            (item["id"], item["title"]) for item in raw.get("model_sections", ())
        )
        self.anchor_aliases: dict[str, str] = dict(raw["anchor_aliases"])
        self.categories: tuple[Category, ...] = tuple(
            sorted(
                (
                    Category(c["id"], c["name"], c["description"], c["order"])
                    for c in raw["categories"]
                ),
                key=lambda item: item.order,
            )
        )
        self.planned_models: tuple[dict[str, str], ...] = tuple(raw.get("planned_models", ()))
        self.concepts: dict[str, Concept] = {
            item["id"]: Concept(
                id=item["id"],
                name=item["name"],
                category=item["category"],
                summary=item["summary"],
                article=item["article"],
                anchor=item.get("anchor"),
                related=tuple(item["related"]),
                models=tuple(item["models"]),
                bibliography=tuple(item["bibliography"]),
                layout=item.get("layout", "concept"),
            )
            for item in raw["concepts"]
        }
        self.bibliography: dict[str, BibEntry] = {
            key: BibEntry(key, value) for key, value in bibliography["entries"].items()
        }

    def sections_for(self, concept: Concept) -> tuple[tuple[str, str], ...]:
        return self.model_sections if concept.layout == "model" else self.sections

    def category(self, category_id: str) -> Category | None:
        return next((item for item in self.categories if item.id == category_id), None)

    def articles(self, category_id: str | None = None) -> list[Concept]:
        return [
            concept
            for concept in self.concepts.values()
            if not concept.is_alias and (category_id is None or concept.category == category_id)
        ]

    def article_path(self, concept: Concept) -> Path:
        target = self.concepts[concept.article]
        return self.content_dir / "articles" / target.category / f"{target.id}.html"

    def resolve_anchor(self, concept: Concept, anchor: str | None) -> str | None:
        if anchor is None:
            return concept.anchor
        alias = self.anchor_aliases.get(anchor)
        if alias is not None:
            return alias.replace("{article}", concept.article)
        return anchor

    def url(self, concept_id: str, anchor: str | None = None) -> str:
        concept = self.concepts.get(concept_id)
        if concept is None:
            raise KeyError(f"nieznane pojęcie matematyczne: {concept_id}")
        target = self.concepts[concept.article]
        path = f"{self.base_path}/{target.category}/{target.id}/"
        fragment = self.resolve_anchor(concept, anchor)
        return f"{path}#{fragment}" if fragment else path

    def article_html(self, concept: Concept) -> str:
        return read_article(self.article_path(concept))

    def checksum(self) -> str:
        digest = hashlib.sha256()
        for path in sorted(self.content_dir.rglob("*")):
            if path.is_file() and path.name != "CHECKSUM":
                digest.update(path.relative_to(self.content_dir).as_posix().encode())
                digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
        return digest.hexdigest()


@cache
def read_article(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@cache
def default_registry() -> MathRegistry:
    return MathRegistry()


class _IdCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.sections: list[str] = []
        self.concept_links: list[tuple[str, str | None]] = []
        self.bib_keys: list[str] = []
        self.plots: list[str] = []
        self.eqrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        identifier = values.get("id")
        if identifier:
            self.ids.append(identifier)
            if tag == "section":
                self.sections.append(identifier)
        concept = values.get("data-concept")
        if concept:
            self.concept_links.append((concept, values.get("data-anchor")))
        bib = values.get("data-bib")
        if bib:
            self.bib_keys.append(bib)
        plot = values.get("data-plot")
        if plot:
            self.plots.append(plot)
        classes = (values.get("class") or "").split()
        if tag == "a" and "ml-eqref" in classes and (values.get("href") or "").startswith("#"):
            self.eqrefs.append(str(values["href"])[1:])


PLOT_TYPES = frozenset(
    {
        "normal",
        "beta",
        "beta-mean",
        "binomial",
        "betabinomial",
        "negbinomial",
        "logistic",
        "beta-update",
        "shrinkage",
    }
)
_FORBIDDEN_LATEX = re.compile(r"\\(label|eqref|tag)\{|\\begin\{(align|equation)\*?\}")


@dataclass(frozen=True)
class ArticleProblem:
    article: str
    message: str


class ArticleValidator:
    def __init__(self, registry: MathRegistry) -> None:
        self._registry = registry

    def ids_of(self, concept: Concept) -> list[str]:
        collector = _IdCollector()
        collector.feed(self._registry.article_html(concept))
        return collector.ids

    def validate(self) -> list[ArticleProblem]:
        problems: list[ArticleProblem] = []
        registry = self._registry
        anchors: dict[str, set[str]] = {}
        for concept in registry.articles():
            path = registry.article_path(concept)
            if not path.exists():
                problems.append(ArticleProblem(concept.id, "brak pliku artykułu"))
                continue
            html = registry.article_html(concept)
            collector = _IdCollector()
            collector.feed(html)
            anchors[concept.id] = set(collector.ids)
            expected_sections = [section for section, _ in registry.sections_for(concept)]
            if collector.sections != expected_sections:
                problems.append(
                    ArticleProblem(concept.id, f"sekcje {collector.sections} ≠ {expected_sections}")
                )
            duplicates = {item for item in collector.ids if collector.ids.count(item) > 1}
            if duplicates:
                problems.append(ArticleProblem(concept.id, f"zdublowane id: {sorted(duplicates)}"))
            if f"eq-{concept.id}" not in collector.ids:
                problems.append(ArticleProblem(concept.id, f"brak głównego wzoru eq-{concept.id}"))
            for key in collector.bib_keys:
                if key not in registry.bibliography:
                    problems.append(ArticleProblem(concept.id, f"nieznane źródło: {key}"))
            for plot in collector.plots:
                if plot not in PLOT_TYPES:
                    problems.append(ArticleProblem(concept.id, f"nieznany typ wykresu: {plot}"))
            for ref in collector.eqrefs:
                if ref not in collector.ids:
                    problems.append(
                        ArticleProblem(concept.id, f"odwołanie do brakującego wzoru #{ref}")
                    )
            if _FORBIDDEN_LATEX.search(html):
                problems.append(ArticleProblem(concept.id, "niedozwolona konstrukcja LaTeX"))
            if "/matematyka/" in html:
                problems.append(ArticleProblem(concept.id, "ręcznie wpisany URL /matematyka/"))
        for concept in registry.articles():
            html_path = registry.article_path(concept)
            if not html_path.exists():
                continue
            collector = _IdCollector()
            collector.feed(registry.article_html(concept))
            for target, anchor in collector.concept_links:
                linked = registry.concepts.get(target)
                if linked is None:
                    problems.append(
                        ArticleProblem(concept.id, f"link do nieznanego pojęcia {target}")
                    )
                    continue
                fragment = registry.resolve_anchor(linked, anchor)
                if fragment and fragment not in anchors.get(linked.article, set()):
                    problems.append(
                        ArticleProblem(
                            concept.id, f"link do brakującej kotwicy {target}#{fragment}"
                        )
                    )
        for concept in registry.concepts.values():
            if concept.is_alias and concept.anchor not in anchors.get(concept.article, set()):
                problems.append(
                    ArticleProblem(
                        concept.id, f"alias bez kotwicy {concept.article}#{concept.anchor}"
                    )
                )
        return problems
