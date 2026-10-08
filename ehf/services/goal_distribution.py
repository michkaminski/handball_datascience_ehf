from __future__ import annotations

from typing import Protocol

from ehf.domain.goal_distribution import (
    GoalDistributionFilters,
    GoalDistributionReport,
    GoalFilterChoices,
    GoalMatch,
    GoalScoreline,
    SeriesKind,
    require_goals,
    series_from_scorelines,
)
from ehf.domain.matches import Choice

REPORT_GENDERS = (
    Choice("men", "Men"),
    Choice("women", "Women"),
)


class GoalDistributionReader(Protocol):
    def fetch_choices(self) -> GoalFilterChoices: ...

    def fetch_scorelines(self, filters: GoalDistributionFilters) -> tuple[GoalScoreline, ...]: ...

    def fetch_matches(
        self, filters: GoalDistributionFilters, kind: SeriesKind, goals: int
    ) -> tuple[GoalMatch, ...]: ...


class GoalDistributionService:
    def __init__(self, reader: GoalDistributionReader) -> None:
        self._reader = reader

    def choices(self) -> GoalFilterChoices:
        return self._reader.fetch_choices()

    def genders(self) -> tuple[Choice, ...]:
        return REPORT_GENDERS

    def report(self, filters: GoalDistributionFilters) -> GoalDistributionReport:
        total, home, away = series_from_scorelines(self._reader.fetch_scorelines(filters))
        return GoalDistributionReport(total, home, away)

    def matches(
        self, filters: GoalDistributionFilters, kind: SeriesKind, goals: int
    ) -> tuple[GoalMatch, ...]:
        return self._reader.fetch_matches(filters, kind, require_goals(goals))
