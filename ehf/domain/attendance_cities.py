from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import TypeVar

from ehf.domain.attendance_city_breakdown import (
    AttendanceFigureLabels,
    CityCompetition,
    CitySeason,
    CityVenue,
    validate_counts,
)
from ehf.domain.attendance_city_names import normalize_city_key
from ehf.domain.goal_distribution import format_int

CITY_LIMIT = 100
CONTRIBUTION_LIMIT = 300
BREAKDOWN_LIMIT = 600
CITY_CHART_LIMIT = 15
UNKNOWN_CLUB_NAME = "—"
CITY_SOURCE_NOTE = (
    "City is taken from the match venue (clubs have no city in the archive). "
    "This shows where spectators attended."
)
CITY_NAMES_NOTE = (
    "City names are merged ignoring case and extra spaces; the most common spelling is shown."
)

CityRow = TypeVar("CityRow")


@dataclass(frozen=True)
class CityAttendance(AttendanceFigureLabels):
    city: str
    played: int
    known: int
    total: int
    mean: float | None
    median: float | None
    mode: int | None
    maximum: int | None
    club_count: int
    competition_count: int

    def __post_init__(self) -> None:
        validate_counts(self.played, self.known, self.total)
        if self.club_count < 0 or self.competition_count < 0:
            raise ValueError("totals and counts cannot be negative")

    @property
    def key(self) -> str:
        return normalize_city_key(self.city)

    @property
    def club_count_label(self) -> str:
        return format_int(self.club_count)

    @property
    def competition_count_label(self) -> str:
        return format_int(self.competition_count)


@dataclass(frozen=True)
class CityContribution(AttendanceFigureLabels):
    city: str
    club_id: int | None
    club_name: str
    competition: str
    played: int
    known: int
    total: int
    mean: float | None
    maximum: int | None
    median: float | None = None
    mode: int | None = None

    def __post_init__(self) -> None:
        validate_counts(self.played, self.known, self.total)


@dataclass(frozen=True)
class CityBundle:
    cities: tuple[CityAttendance, ...] = ()
    contributions: tuple[CityContribution, ...] = ()
    seasons: tuple[CitySeason, ...] = ()
    competitions: tuple[CityCompetition, ...] = ()
    venues: tuple[CityVenue, ...] = ()
    matches_without_city: int = 0


@dataclass(frozen=True)
class CityReport:
    cities: tuple[CityAttendance, ...]
    contributions: tuple[CityContribution, ...]
    matches_without_city: int
    seasons: tuple[CitySeason, ...] = ()
    competitions: tuple[CityCompetition, ...] = ()
    venues: tuple[CityVenue, ...] = ()
    source_note: str = CITY_SOURCE_NOTE
    names_note: str = CITY_NAMES_NOTE

    def __post_init__(self) -> None:
        if self.matches_without_city < 0:
            raise ValueError("matches without city cannot be negative")

    @property
    def is_empty(self) -> bool:
        return not self.cities

    @property
    def chart_cities(self) -> tuple[CityAttendance, ...]:
        return self.cities[:CITY_CHART_LIMIT]

    @property
    def matches_without_city_label(self) -> str:
        return format_int(self.matches_without_city)

    @property
    def missing_city_note(self) -> str:
        if self.matches_without_city == 0:
            return "Every played match for the selected filters has a venue city."
        return (
            f"{self.matches_without_city_label} played matches have no venue city "
            "and are excluded from the city ranking."
        )

    @property
    def ranking_note(self) -> str:
        return (
            f"Top {len(self.cities)} cities by total spectators; only matches with known attendance "
            "are summed."
        )

    @property
    def contributions_note(self) -> str:
        return (
            "Home club × competition rows that generated the attendance in the ranked cities "
            f"({len(self.contributions)} rows, grouped by city rank, highest total first)."
        )

    @property
    def seasons_note(self) -> str:
        return (
            f"Season by season attendance in the ranked cities ({len(self.seasons)} rows, "
            "grouped by city rank, oldest season first)."
        )

    @property
    def competitions_note(self) -> str:
        return (
            f"Attendance by competition in the ranked cities ({len(self.competitions)} rows, "
            "grouped by city rank, highest total first)."
        )

    @property
    def venues_note(self) -> str:
        return (
            f"Venues located in the ranked cities ({len(self.venues)} rows, "
            "grouped by city rank, highest total first)."
        )

    def seasons_of(self, city: str) -> tuple[CitySeason, ...]:
        return tuple(item for item in self.seasons if item.city == city)

    def competitions_of(self, city: str) -> tuple[CityCompetition, ...]:
        return tuple(item for item in self.competitions if item.city == city)

    def venues_of(self, city: str) -> tuple[CityVenue, ...]:
        return tuple(item for item in self.venues if item.city == city)

    @classmethod
    def empty(cls, matches_without_city: int = 0) -> CityReport:
        return cls(cities=(), contributions=(), matches_without_city=matches_without_city)


class CityCalculator:
    @staticmethod
    def build(
        bundle: CityBundle,
        city_limit: int = CITY_LIMIT,
        contribution_limit: int = CONTRIBUTION_LIMIT,
        breakdown_limit: int = BREAKDOWN_LIMIT,
    ) -> CityReport:
        ranked = CityCalculator.rank_cities(bundle.cities, city_limit)
        return CityReport(
            cities=ranked,
            contributions=CityCalculator.rank_contributions(
                bundle.contributions, ranked, contribution_limit
            ),
            matches_without_city=bundle.matches_without_city,
            seasons=CityCalculator.rank_seasons(bundle.seasons, ranked, breakdown_limit),
            competitions=CityCalculator.rank_competitions(
                bundle.competitions, ranked, breakdown_limit
            ),
            venues=CityCalculator.rank_venues(bundle.venues, ranked, breakdown_limit),
        )

    @staticmethod
    def rank_cities(
        cities: Sequence[CityAttendance], limit: int = CITY_LIMIT
    ) -> tuple[CityAttendance, ...]:
        eligible = [item for item in cities if item.known > 0 and item.key]
        eligible.sort(key=lambda item: (-item.total, -item.known, item.key))
        return tuple(eligible[:limit])

    @staticmethod
    def rank_contributions(
        contributions: Sequence[CityContribution],
        ranked_cities: Sequence[CityAttendance],
        limit: int = CONTRIBUTION_LIMIT,
    ) -> tuple[CityContribution, ...]:
        order, rows = CityCalculator._in_ranked_cities(contributions, ranked_cities)
        eligible = [item for item in rows if item.known > 0]
        eligible.sort(
            key=lambda item: (
                -item.total,
                order[normalize_city_key(item.city)],
                item.club_name.casefold(),
                item.competition.casefold(),
            )
        )
        top = eligible[:limit]
        top.sort(
            key=lambda item: (
                order[normalize_city_key(item.city)],
                -item.total,
                item.club_name.casefold(),
                item.competition.casefold(),
            )
        )
        return tuple(top)

    @staticmethod
    def rank_seasons(
        seasons: Sequence[CitySeason],
        ranked_cities: Sequence[CityAttendance],
        limit: int = BREAKDOWN_LIMIT,
    ) -> tuple[CitySeason, ...]:
        order, rows = CityCalculator._in_ranked_cities(seasons, ranked_cities)
        eligible = [item for item in rows if item.known > 0]
        eligible.sort(
            key=lambda item: (order[normalize_city_key(item.city)], item.year_start, item.season_code)
        )
        return tuple(eligible[:limit])

    @staticmethod
    def rank_competitions(
        competitions: Sequence[CityCompetition],
        ranked_cities: Sequence[CityAttendance],
        limit: int = BREAKDOWN_LIMIT,
    ) -> tuple[CityCompetition, ...]:
        order, rows = CityCalculator._in_ranked_cities(competitions, ranked_cities)
        eligible = [item for item in rows if item.known > 0]
        eligible.sort(
            key=lambda item: (
                order[normalize_city_key(item.city)],
                -item.total,
                item.competition.casefold(),
            )
        )
        return tuple(eligible[:limit])

    @staticmethod
    def rank_venues(
        venues: Sequence[CityVenue],
        ranked_cities: Sequence[CityAttendance],
        limit: int = BREAKDOWN_LIMIT,
    ) -> tuple[CityVenue, ...]:
        order, rows = CityCalculator._in_ranked_cities(venues, ranked_cities)
        eligible = [item for item in rows if item.known > 0]
        eligible.sort(
            key=lambda item: (
                order[normalize_city_key(item.city)],
                -item.total,
                item.venue_name.casefold(),
                item.venue_id,
            )
        )
        return tuple(eligible[:limit])

    @staticmethod
    def _in_ranked_cities(
        rows: Sequence[CityRow], ranked_cities: Sequence[CityAttendance]
    ) -> tuple[dict[str, int], list[CityRow]]:
        order = {item.key: position for position, item in enumerate(ranked_cities)}
        display = {item.key: item.city for item in ranked_cities}
        matched = [
            replace(row, city=display[normalize_city_key(row.city)])
            for row in rows
            if normalize_city_key(row.city) in order
        ]
        return order, matched
