from __future__ import annotations

from collections.abc import Callable

from flask import Response, abort, jsonify, request
from flask.views import MethodView

from ehf.domain.attendance_appeal import appeal_model
from ehf.services.attendance_appeal import AppealModelMissing, AttendanceAppealService
from maf.forecast import ForecastScenario, parse_hour

JsonDict = dict[str, object]


def _error(code: int, message: str) -> Response:
    response = jsonify({"error": message})
    response.status_code = code
    return response


def _int_arg(name: str) -> int:
    value = request.args.get(name, "")
    if not value.lstrip("-").isdigit():
        abort(400, description=f"parameter {name} must be an integer")
    return int(value)


def _optional_int_arg(name: str) -> int | None:
    return _int_arg(name) if request.args.get(name, "").strip() else None


class _AppealApiView(MethodView):
    def __init__(self, service: AttendanceAppealService) -> None:
        self._service = service

    def _respond(self, action: Callable[[str], JsonDict]) -> Response:
        key = appeal_model(request.args.get("model")).spec.key
        try:
            result = action(key)
        except AppealModelMissing:
            return _error(404, f"Model {key} has not been trained yet. Run: python scripts/train_maf.py {key}")
        except KeyError as exc:
            return _error(404, f"Not found in the model: {exc}")
        except ValueError as exc:
            return _error(400, str(exc))
        return jsonify(result)


class AppealPanelView(_AppealApiView):
    def get(self) -> Response:
        return self._respond(self._service.panel)


class AppealClubView(_AppealApiView):
    def get(self, club_id: int) -> Response:
        return self._respond(lambda key: self._service.club(key, club_id))


class AppealHostView(_AppealApiView):
    def get(self, club_id: int) -> Response:
        return self._respond(lambda key: self._service.host(key, club_id))


class AppealCompareView(_AppealApiView):
    def get(self) -> Response:
        first, second = _int_arg("a"), _int_arg("b")
        return self._respond(lambda key: self._service.compare(key, first, second))


class AppealForecastView(_AppealApiView):
    def get(self) -> Response:
        try:
            hour = parse_hour(request.args.get("hour") or None)
        except ValueError:
            return _error(400, "hour must be HH:MM")
        weekday = _int_arg("weekday")
        if not 0 <= weekday <= 6:
            return _error(400, "weekday must be 0–6")
        scenario = ForecastScenario(
            host_id=_int_arg("host"),
            opponent_id=_int_arg("opponent"),
            competition_key=request.args.get("competition") or None,
            season_key=request.args.get("season") or None,
            capacity=_optional_int_arg("capacity"),
            weekday=weekday,
            hour=hour,
            phase=request.args.get("phase", "regular"),
            threshold=_optional_int_arg("threshold"),
        )
        return self._respond(lambda key: self._service.forecast(key, scenario))


class AppealExportView(MethodView):
    def __init__(self, service: AttendanceAppealService) -> None:
        self._service = service

    def get(self) -> Response:
        key = appeal_model(request.args.get("model")).spec.key
        try:
            content = self._service.export_csv(key)
        except AppealModelMissing:
            abort(404)
        return Response(
            "﻿" + content,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename=maf_{key}.csv"},
        )
