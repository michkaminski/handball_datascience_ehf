from __future__ import annotations

from flask import abort, render_template, request
from flask.views import MethodView

from ehf.domain.errors import DataReadError
from ehf.domain.match_sheet import TOP_SCORERS, MatchSheetOptions
from ehf.interface.match_sheet_filters import match_sheet_request_from_args
from ehf.services.match_sheet import MatchSheetService


def _request_or_400():
    try:
        return match_sheet_request_from_args(request.args)
    except ValueError as exc:
        abort(400, description=str(exc))


class MatchSheetFormView(MethodView):
    def __init__(self, service: MatchSheetService) -> None:
        self._service = service

    def get(self) -> str:
        sheet_request = _request_or_400()
        try:
            options = self._service.options(sheet_request)
            error = None
        except DataReadError as exc:
            options = MatchSheetOptions(seasons=(), competitions=(), teams=(), venues=())
            error = str(exc)
        season_id = sheet_request.season_id
        if season_id is None and options.seasons:
            season_id = int(options.seasons[0].value)
        return render_template(
            "pages/match_sheet.html",
            sekcja_aktywna="protokol",
            options=options,
            sheet_request=sheet_request,
            season_id=season_id,
            error=error,
        )


class MatchSheetPrintView(MethodView):
    def __init__(self, service: MatchSheetService) -> None:
        self._service = service

    def get(self) -> str:
        sheet_request = _request_or_400()
        try:
            sheet = self._service.build(sheet_request)
        except ValueError as exc:
            abort(400, description=str(exc))
        except DataReadError as exc:
            abort(503, description=str(exc))
        return render_template("print/match_sheet.html", sheet=sheet, top_scorers=TOP_SCORERS)
