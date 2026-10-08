from __future__ import annotations

from flask import abort, render_template, request
from flask.views import MethodView

from ehf.domain.database_stats import DatabaseStatsPage, DatabaseSummary
from ehf.domain.errors import DataReadError
from ehf.interface.database_stats_filters import database_stats_filters_from_args
from ehf.services.database_stats import DatabaseStatsService

EMPTY_SUMMARY = DatabaseSummary(
    name="—",
    size_bytes=0,
    table_count=0,
    row_total=0,
    tables_bytes=0,
    indexes_bytes=0,
)


class DatabaseStatsView(MethodView):
    def __init__(self, service: DatabaseStatsService) -> None:
        self._service = service

    def get(self) -> str:
        try:
            filters = database_stats_filters_from_args(request.args)
        except ValueError as exc:
            abort(400, description=str(exc))
        try:
            page = self._service.list_stats(filters)
            error = None
        except DataReadError as exc:
            page = DatabaseStatsPage(
                summary=EMPTY_SUMMARY,
                items=(),
                schemas=(),
                filters=filters,
                filtered_count=0,
            )
            error = str(exc)
        options = self._service.filter_options(page.schemas)
        return render_template(
            "pages/database_stats.html",
            sekcja_aktywna="statystyki_bazy",
            page=page,
            options=options,
            filters=filters,
            error=error,
        )
