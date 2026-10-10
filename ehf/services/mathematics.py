from __future__ import annotations

from dataclasses import dataclass

from mathlib.registry import Category, Concept, MathRegistry
from mathlib.render import ArticleRenderer, RenderedArticle


@dataclass(frozen=True)
class MathCategory:
    category: Category
    articles: tuple[Concept, ...]


@dataclass(frozen=True)
class ArticlePage:
    article: RenderedArticle
    category: Category
    previous: Concept | None
    next: Concept | None
    related: tuple[Concept, ...]
    used_by: tuple[str, ...]


class MathLibraryService:
    def __init__(self, registry: MathRegistry) -> None:
        self._registry = registry
        self._renderer = ArticleRenderer(registry)

    @property
    def registry(self) -> MathRegistry:
        return self._registry

    def categories(self) -> tuple[MathCategory, ...]:
        return tuple(
            MathCategory(category, tuple(self._registry.articles(category.id)))
            for category in self._registry.categories
        )

    def category(self, category_id: str) -> MathCategory | None:
        category = self._registry.category(category_id)
        if category is None:
            return None
        return MathCategory(category, tuple(self._registry.articles(category.id)))

    def article(self, category_id: str, slug: str) -> ArticlePage | None:
        concept = self._registry.concepts.get(slug)
        if concept is None or concept.is_alias or concept.category != category_id:
            return None
        category = self._registry.category(category_id)
        if category is None or not self._registry.article_path(concept).exists():
            return None
        siblings = self._registry.articles(category_id)
        position = siblings.index(concept)
        return ArticlePage(
            article=self._renderer.render(concept),
            category=category,
            previous=siblings[position - 1] if position > 0 else None,
            next=siblings[position + 1] if position + 1 < len(siblings) else None,
            related=tuple(
                self._registry.concepts[item]
                for item in concept.related
                if item in self._registry.concepts
            ),
            used_by=concept.models,
        )

    def links(self, concept_ids: tuple[str, ...]) -> dict[str, dict[str, object]]:
        result: dict[str, dict[str, object]] = {}
        for concept_id in concept_ids:
            concept = self._registry.concepts[concept_id]
            result[concept_id] = {
                "name": concept.name,
                "summary": concept.summary,
                "url": self._registry.url(concept_id),
                "anchors": {
                    "definition": self._registry.url(concept_id, "definicja"),
                    "formula": self._registry.url(concept_id, "wzor"),
                    "derivation": self._registry.url(concept_id, "wyprowadzenie"),
                    "example": self._registry.url(concept_id, "przyklad"),
                },
            }
        return result
