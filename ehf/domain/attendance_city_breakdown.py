from __future__ import annotations

from dataclasses import dataclass

from ehf.domain.attendance_analytics import format_optional_int, format_rounded
from ehf.domain.goal_distribution import format_int


def validate_counts(played: int, known: int, total: int = 0) -> None:
    if played < 0 or known < 0:
        raise ValueError("match counts cannot be negative")
    if known > played:
        raise ValueError("known matches cannot exceed played matches")
    if total < 0:
        raise ValueError("total cannot be negative")


class AttendanceFigureLabels:
    played: int
    known: int
    total: int
    mean: float | None
    median: float | None
    mode: int | None
    maximum: int | None

    @property
    def played_label(self) -> str:
        return format_int(self.played)

    @property
    def known_label(self) -> str:
        return format_int(self.known)

    @property
    def total_label(self) -> str:
        return format_int(self.total)

    @property
    def mean_label(self) -> str:
        return format_rounded(self.mean)

    @property
    def median_label(self) -> str:
        return format_rounded(self.median)

    @property
    def mode_label(self) -> str:
        return format_optional_int(self.mode)

    @property
    def maximum_label(self) -> str:
        return format_optional_int(self.maximum)


@dataclass(frozen=True)
class CitySeason(AttendanceFigureLabels):
    city: str
    season_code: str
    year_start: int
    played: int
    known: int
    total: int
    mean: float | None
    median: float | None
    maximum: int | None
    mode: int | None = None

    def __post_init__(self) -> None:
        validate_counts(self.played, self.known, self.total)


@dataclass(frozen=True)
class CityCompetition(AttendanceFigureLabels):
    city: str
    competition: str
    played: int
    known: int
    total: int
    mean: float | None
    median: float | None
    maximum: int | None
    mode: int | None = None

    def __post_init__(self) -> None:
        validate_counts(self.played, self.known, self.total)


@dataclass(frozen=True)
class CityVenue(AttendanceFigureLabels):
    city: str
    venue_id: int
    venue_name: str
    played: int
    known: int
    total: int
    mean: float | None
    maximum: int | None
    median: float | None = None
    mode: int | None = None

    def __post_init__(self) -> None:
        validate_counts(self.played, self.known, self.total)
