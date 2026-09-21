from __future__ import annotations

from flask import abort, render_template, request
from flask.views import MethodView

from ehf.domain.errors import DataReadError, RefereeNotFound
from ehf.domain.referees import (
    RefereeFilterOptions,
    RefereeListPage,
    RefereeMatchFilterOptions,
    RefereeMatchFilters,
    RefereeMatchPage,
)
from ehf.interface.expand import expanded_keys
from ehf.interface.referee_filters import referee_filters_from_args, referee_match_filters_from_args
from ehf.services.referee_detail import RefereeDetailService
from ehf.services.referee_list import RefereeListService


class RefereeListView(MethodView):
    def __init__(self, service: RefereeListService) -> None:
        self._service = service

    def get(self) -> str:
        try:
            filters = referee_filters_from_args(request.args)
        except ValueError as exc:
            abort(400, description=str(exc))
        try:
            page = self._service.list_referees(filters)
            options = self._service.filter_options()
            error = None
        except DataReadError as exc:
            page = RefereeListPage(items=(), total=0, filters=filters)
            options = RefereeFilterOptions(countries=())
            error = str(exc)
        return render_template(
            "pages/referees.html",
            sekcja_aktywna="sedziowie",
            page=page,
            options=options,
            filters=filters,
            error=error,
        )


class RefereeDetailView(MethodView):
    def __init__(self, service: RefereeDetailService) -> None:
        self._service = service

    def get(self, referee_id: int) -> str:
        try:
            match_filters = referee_match_filters_from_args(request.args)
        except ValueError as exc:
            abort(400, description=str(exc))
        try:
            card = self._service.get_card(referee_id, match_filters, expanded_keys(request.args))
            error = None
        except RefereeNotFound:
            abort(404)
        except DataReadError as exc:
            card = None
            error = str(exc)
        return render_template(
            "pages/referee_detail.html",
            sekcja_aktywna="sedziowie",
            card=card,
            profile=None if card is None else card.profile,
            matches=RefereeMatchPage(items=(), total=0, filters=match_filters) if card is None else card.matches,
            match_options=RefereeMatchFilterOptions(seasons=(), competitions=(), clubs=())
            if card is None
            else card.match_options,
            match_filters=match_filters,
            stats=None if card is None else card.stats,
            active_tab=request.args.get("tab") or "data",
            error=error,
        )
