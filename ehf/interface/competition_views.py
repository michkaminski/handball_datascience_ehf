from __future__ import annotations

from flask import abort, render_template, request
from flask.views import MethodView

from ehf.domain.competitions import CompetitionFilterOptions, CompetitionListPage
from ehf.domain.errors import DataReadError
from ehf.interface.competition_filters import competition_filters_from_args
from ehf.services.competition_list import CompetitionListService


class CompetitionListView(MethodView):
    def __init__(self, service: CompetitionListService) -> None:
        self._service = service

    def get(self) -> str:
        try:
            filters = competition_filters_from_args(request.args)
        except ValueError as exc:
            abort(400, description=str(exc))
        try:
            page = self._service.list_competitions(filters)
            options = self._service.filter_options()
            error = None
        except DataReadError as exc:
            page = CompetitionListPage(items=(), total=0, filters=filters)
            options = CompetitionFilterOptions(seasons=())
            error = str(exc)
        return render_template(
            "pages/competitions.html",
            sekcja_aktywna="rozgrywki",
            page=page,
            options=options,
            filters=filters,
            error=error,
        )
