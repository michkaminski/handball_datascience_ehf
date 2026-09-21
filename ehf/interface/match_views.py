from __future__ import annotations

from flask import abort, render_template, request
from flask.views import MethodView

from ehf.domain.errors import DataReadError, MatchNotFound
from ehf.domain.matches import MatchFilterOptions, MatchListPage
from ehf.interface.match_filters import match_filters_from_args
from ehf.interface.positions import legend_for_lineups
from ehf.services.match_detail import MatchDetailService
from ehf.services.match_list import MatchListService


class MatchListView(MethodView):
    def __init__(self, service: MatchListService) -> None:
        self._service = service

    def get(self) -> str:
        try:
            filters = match_filters_from_args(request.args)
        except ValueError as exc:
            abort(400, description=str(exc))
        try:
            page = self._service.list_matches(filters)
            options = self._service.filter_options()
            error = None
        except DataReadError as exc:
            page = MatchListPage(items=(), total=0, filters=filters)
            options = MatchFilterOptions(
                seasons=(),
                competitions=(),
                phases=(),
                groups=(),
                venues=(),
            )
            error = str(exc)
        return render_template(
            "pages/matches.html",
            sekcja_aktywna="mecze",
            page=page,
            options=options,
            filters=filters,
            error=error,
        )


class MatchDetailView(MethodView):
    def __init__(self, service: MatchDetailService) -> None:
        self._service = service

    def get(self, match_id: int) -> str:
        try:
            match = self._service.get_match(match_id)
            error = None
        except MatchNotFound:
            abort(404)
        except DataReadError as exc:
            match = None
            error = str(exc)
        legend = ()
        if match is not None:
            legend = legend_for_lineups(match.home_lineup, match.away_lineup)
        return render_template(
            "pages/match_detail.html",
            sekcja_aktywna="mecze",
            match=match,
            position_legend=legend,
            error=error,
        )
