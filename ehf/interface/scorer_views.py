from __future__ import annotations

from flask import abort, render_template, request
from flask.views import MethodView

from ehf.domain.errors import DataReadError
from ehf.domain.scorers import ScorerFilterOptions, ScorerListPage
from ehf.interface.scorer_filters import scorer_filters_from_args
from ehf.services.scorer_list import ScorerListService


class ScorerListView(MethodView):
    def __init__(self, service: ScorerListService) -> None:
        self._service = service

    def get(self) -> str:
        try:
            filters = scorer_filters_from_args(request.args)
        except ValueError as exc:
            abort(400, description=str(exc))
        try:
            page = self._service.list_scorers(filters)
            options = self._service.filter_options()
            error = None
        except DataReadError as exc:
            page = ScorerListPage(items=(), total=0, filters=filters)
            options = ScorerFilterOptions(seasons=(), competitions=())
            error = str(exc)
        return render_template(
            "pages/scorers.html",
            sekcja_aktywna="strzelcy",
            page=page,
            options=options,
            filters=filters,
            error=error,
        )
