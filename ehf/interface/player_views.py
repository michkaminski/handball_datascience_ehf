from __future__ import annotations

from flask import abort, render_template, request
from flask.views import MethodView

from ehf.domain.errors import DataReadError, PlayerNotFound
from ehf.domain.players import (
    PlayerFilterOptions,
    PlayerListPage,
    PlayerMatchFilterOptions,
    PlayerMatchFilters,
    PlayerMatchPage,
)
from ehf.interface.player_filters import player_filters_from_args, player_match_filters_from_args
from ehf.services.player_detail import PlayerDetailService
from ehf.services.player_list import PlayerListService


class PlayerListView(MethodView):
    def __init__(self, service: PlayerListService) -> None:
        self._service = service

    def get(self) -> str:
        try:
            filters = player_filters_from_args(request.args)
        except ValueError as exc:
            abort(400, description=str(exc))
        try:
            page = self._service.list_players(filters)
            options = self._service.filter_options()
            error = None
        except DataReadError as exc:
            page = PlayerListPage(items=(), total=0, filters=filters)
            options = PlayerFilterOptions(
                seasons=(),
                competitions=(),
                clubs=(),
                positions=(),
                birth_years=(),
            )
            error = str(exc)
        return render_template(
            "pages/players.html",
            sekcja_aktywna="zawodnicy",
            page=page,
            options=options,
            filters=filters,
            error=error,
        )


class PlayerDetailView(MethodView):
    def __init__(self, service: PlayerDetailService) -> None:
        self._service = service

    def get(self, player_id: int) -> str:
        try:
            match_filters = player_match_filters_from_args(request.args)
        except ValueError as exc:
            abort(400, description=str(exc))
        try:
            card = self._service.get_card(player_id, match_filters)
            error = None
        except PlayerNotFound:
            abort(404)
        except DataReadError as exc:
            card = None
            error = str(exc)
        return render_template(
            "pages/player_detail.html",
            sekcja_aktywna="zawodnicy",
            card=card,
            profile=None if card is None else card.profile,
            seasons=() if card is None else card.seasons,
            matches=PlayerMatchPage(items=(), total=0, filters=match_filters) if card is None else card.matches,
            match_options=PlayerMatchFilterOptions(seasons=(), competitions=(), clubs=())
            if card is None
            else card.match_options,
            match_filters=match_filters,
            active_tab=request.args.get("tab") or "profile",
            error=error,
        )
