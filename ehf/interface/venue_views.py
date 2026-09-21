from __future__ import annotations

from flask import abort, render_template, request
from flask.views import MethodView

from ehf.domain.errors import DataReadError, VenueNotFound
from ehf.domain.venues import (
    VenueFilterOptions,
    VenueListPage,
    VenueMatchFilterOptions,
    VenueMatchFilters,
    VenueMatchPage,
    VenuePlayerFilters,
    VenuePlayerPage,
)
from ehf.interface.expand import expanded_keys
from ehf.interface.venue_filters import (
    venue_filters_from_args,
    venue_match_filters_from_args,
    venue_player_filters_from_args,
)
from ehf.services.venue_detail import VenueDetailService
from ehf.services.venue_list import VenueListService


class VenueListView(MethodView):
    def __init__(self, service: VenueListService) -> None:
        self._service = service

    def get(self) -> str:
        try:
            filters = venue_filters_from_args(request.args)
        except ValueError as exc:
            abort(400, description=str(exc))
        try:
            page = self._service.list_venues(filters)
            options = self._service.filter_options()
            error = None
        except DataReadError as exc:
            page = VenueListPage(items=(), total=0, filters=filters)
            options = VenueFilterOptions(cities=())
            error = str(exc)
        return render_template(
            "pages/venues.html",
            sekcja_aktywna="hale",
            page=page,
            options=options,
            filters=filters,
            error=error,
        )


class VenueDetailView(MethodView):
    def __init__(self, service: VenueDetailService) -> None:
        self._service = service

    def get(self, venue_id: int) -> str:
        try:
            match_filters = venue_match_filters_from_args(request.args)
            player_filters = venue_player_filters_from_args(request.args)
        except ValueError as exc:
            abort(400, description=str(exc))
        try:
            card = self._service.get_card(
                venue_id, match_filters, player_filters, expanded_keys(request.args)
            )
            error = None
        except VenueNotFound:
            abort(404)
        except DataReadError as exc:
            card = None
            error = str(exc)
        return render_template(
            "pages/venue_detail.html",
            sekcja_aktywna="hale",
            card=card,
            profile=None if card is None else card.profile,
            matches=VenueMatchPage(items=(), total=0, filters=match_filters) if card is None else card.matches,
            match_options=VenueMatchFilterOptions(seasons=(), competitions=(), clubs=())
            if card is None
            else card.match_options,
            match_filters=match_filters,
            players=VenuePlayerPage(items=(), total=0, filters=player_filters) if card is None else card.players,
            player_filters=player_filters,
            stats=None if card is None else card.stats,
            active_tab=request.args.get("tab") or "data",
            error=error,
        )
