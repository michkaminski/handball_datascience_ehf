from __future__ import annotations

from flask import abort, render_template, request
from flask.views import MethodView

from ehf.domain.errors import DataReadError
from ehf.domain.seasons import SeasonListPage
from ehf.interface.season_filters import season_filters_from_args
from ehf.services.season_list import SeasonListService


class SeasonListView(MethodView):
    def __init__(self, service: SeasonListService) -> None:
        self._service = service

    def get(self) -> str:
        try:
            filters = season_filters_from_args(request.args)
        except ValueError as exc:
            abort(400, description=str(exc))
        options = self._service.filter_options()
        try:
            page = self._service.list_seasons(filters)
            error = None
        except DataReadError as exc:
            page = SeasonListPage(items=(), total=0, filters=filters)
            error = str(exc)
        return render_template(
            "pages/seasons.html",
            sekcja_aktywna="sezony",
            page=page,
            options=options,
            filters=filters,
            error=error,
        )
