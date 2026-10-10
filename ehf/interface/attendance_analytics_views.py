from __future__ import annotations

from flask import abort, render_template, request
from flask.views import MethodView

from ehf.domain.errors import DataReadError
from ehf.interface.attendance_analytics_chart import attendance_charts_payload
from ehf.interface.attendance_analytics_filters import attendance_filters_from_args
from ehf.services.attendance_analytics import AttendanceAnalyticsService
from ehf.services.attendance_appeal import AttendanceAppealService


class AttendanceAnalyticsView(MethodView):
    def __init__(
        self,
        service: AttendanceAnalyticsService,
        appeal_service: AttendanceAppealService | None = None,
    ) -> None:
        self._service = service
        self._appeal_service = appeal_service

    def get(self) -> str:
        try:
            filters = attendance_filters_from_args(request.args)
        except ValueError as exc:
            abort(400, description=str(exc))
        try:
            choices = self._service.choices()
            report = self._service.report(filters)
        except DataReadError as exc:
            abort(503, description=str(exc))
        return render_template(
            "pages/attendance_analytics.html",
            sekcja_aktywna="attendance",
            report=report,
            filters=filters,
            choices=choices,
            genders=self._service.genders(),
            charts=attendance_charts_payload(report),
            appeal_models=self._appeal_service.models() if self._appeal_service else (),
        )
