from __future__ import annotations

from flask import abort, render_template, request
from flask.views import MethodView

from ehf.domain.errors import DataReadError
from ehf.domain.goal_distribution import series_kind
from ehf.interface.distribution_catalog import DISTRIBUTION_CATALOG
from ehf.interface.goal_distribution_filters import goal_distribution_filters_from_args
from ehf.services.goal_distribution import GoalDistributionService


class DistributionListView(MethodView):
    def get(self) -> str:
        return render_template(
            "pages/distributions.html",
            sekcja_aktywna="rozkłady",
            rozklady=DISTRIBUTION_CATALOG,
        )


class GoalDistributionView(MethodView):
    def __init__(self, service: GoalDistributionService) -> None:
        self._service = service

    def get(self) -> str:
        try:
            filters = goal_distribution_filters_from_args(request.args)
        except ValueError as exc:
            abort(400, description=str(exc))
        try:
            choices = self._service.choices()
            report = self._service.report(filters)
        except DataReadError as exc:
            abort(503, description=str(exc))
        return render_template(
            "pages/goal_distribution.html",
            sekcja_aktywna="rozkłady",
            report=report,
            filters=filters,
            choices=choices,
            genders=self._service.genders(),
        )


class GoalDistributionMatchesView(MethodView):
    def __init__(self, service: GoalDistributionService) -> None:
        self._service = service

    def get(self) -> str:
        try:
            filters = goal_distribution_filters_from_args(request.args)
            kind = series_kind(request.args.get("series"))
            goals = _goals(request.args.get("goals"))
            matches = self._service.matches(filters, kind, goals)
        except ValueError as exc:
            abort(400, description=str(exc))
        except DataReadError as exc:
            abort(503, description=str(exc))
        return render_template("pages/goal_distribution_matches.html", matches=matches)


def _goals(raw: str | None) -> int:
    if raw is None or not raw.isdigit():
        raise ValueError("goals must be a non-negative integer")
    return int(raw)
