from __future__ import annotations

from flask import abort, render_template
from flask.views import MethodView

from ehf.services.mathematics import MathLibraryService

MENU = {"sekcja_aktywna": "matematyka"}


class _MathView(MethodView):
    def __init__(self, service: MathLibraryService) -> None:
        self._service = service


class MathIndexView(_MathView):
    def get(self) -> str:
        registry = self._service.registry
        return render_template(
            "mathematics/index.html",
            categories=self._service.categories(),
            planned=registry.planned_models,
            registry=registry,
            **MENU,
        )


class MathCategoryView(_MathView):
    def get(self, category: str) -> str:
        result = self._service.category(category)
        if result is None:
            abort(404)
        registry = self._service.registry
        return render_template(
            "mathematics/category.html",
            result=result,
            categories=self._service.categories(),
            planned=[item for item in registry.planned_models if item["category"] == category],
            registry=registry,
            **MENU,
        )


class MathArticleView(_MathView):
    def get(self, category: str, slug: str) -> str:
        page = self._service.article(category, slug)
        if page is None:
            abort(404)
        return render_template(
            "mathematics/article.html",
            page=page,
            categories=self._service.categories(),
            registry=self._service.registry,
            **MENU,
        )
