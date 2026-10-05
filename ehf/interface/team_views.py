from __future__ import annotations

from flask import abort, render_template, request
from flask.views import MethodView

from ehf.domain.errors import DataReadError, TeamNotFound
from ehf.domain.gender import GENDER_CHOICES
from ehf.domain.teams import TeamFilterOptions, TeamListPage
from ehf.interface.team_filters import (
    team_detail_filters_from_args,
    team_filters_from_args,
    team_sheet_filters_from_args,
)
from ehf.services.team_detail import TeamDetailService
from ehf.services.team_list import TeamListService


class TeamListView(MethodView):
    def __init__(self, service: TeamListService) -> None:
        self._service = service

    def get(self) -> str:
        try:
            filters = team_filters_from_args(request.args)
        except ValueError as exc:
            abort(400, description=str(exc))
        try:
            page = self._service.list_teams(filters)
            options = self._service.filter_options()
            error = None
        except DataReadError as exc:
            page = TeamListPage(items=(), total=0, filters=filters)
            options = TeamFilterOptions(seasons=(), genders=GENDER_CHOICES)
            error = str(exc)
        return render_template(
            "pages/teams.html",
            sekcja_aktywna="druzyny",
            page=page,
            options=options,
            filters=filters,
            error=error,
        )


class TeamDetailView(MethodView):
    def __init__(self, service: TeamDetailService) -> None:
        self._service = service

    def get(self, club_id: int) -> str:
        try:
            filters = team_detail_filters_from_args(request.args)
            sheet_filters = team_sheet_filters_from_args(request.args)
        except ValueError as exc:
            abort(400, description=str(exc))
        try:
            card = self._service.get_card(club_id, filters, sheet_filters)
            error = None
        except TeamNotFound:
            abort(404)
        except DataReadError as exc:
            card = None
            error = str(exc)
        return render_template(
            "pages/team_detail.html",
            sekcja_aktywna="druzyny",
            card=card,
            profile=None if card is None else card.profile,
            error=error,
        )
