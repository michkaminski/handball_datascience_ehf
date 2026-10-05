from __future__ import annotations

from typing import Mapping

from flask import abort, render_template, request
from flask.views import MethodView

from ehf.domain.errors import DataReadError, TeamNotFound
from ehf.domain.team_report import DEFAULT_LAST_MATCHES, TeamReportOptions, TeamReportRequest
from ehf.interface.query_args import optional_int
from ehf.services.team_report import TeamReportService


def team_report_request_from_args(args: Mapping[str, str]) -> TeamReportRequest:
    return TeamReportRequest(
        club_id=optional_int(args.get("club_id")),
        season_id=optional_int(args.get("season_id")),
        last_matches=optional_int(args.get("last")) or DEFAULT_LAST_MATCHES,
    )


def _request_or_400() -> TeamReportRequest:
    try:
        return team_report_request_from_args(request.args)
    except ValueError as exc:
        abort(400, description=str(exc))


class TeamReportFormView(MethodView):
    def __init__(self, service: TeamReportService) -> None:
        self._service = service

    def get(self) -> str:
        report_request = _request_or_400()
        try:
            options = self._service.options(report_request.season_id)
            error = None
        except DataReadError as exc:
            options = TeamReportOptions(seasons=(), teams=())
            error = str(exc)
        season_id = report_request.season_id
        if season_id is None and options.seasons:
            season_id = int(options.seasons[0].value)
        return render_template(
            "pages/team_report.html",
            sekcja_aktywna="raport_druzyny",
            options=options,
            report_request=report_request,
            season_id=season_id,
            error=error,
        )


class TeamReportPrintView(MethodView):
    def __init__(self, service: TeamReportService) -> None:
        self._service = service

    def get(self) -> str:
        report_request = _request_or_400()
        try:
            report = self._service.build(report_request)
        except TeamNotFound:
            abort(404)
        except ValueError as exc:
            abort(400, description=str(exc))
        except DataReadError as exc:
            abort(503, description=str(exc))
        return render_template("print/team_report.html", report=report)
