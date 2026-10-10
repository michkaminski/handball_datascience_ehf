from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import TYPE_CHECKING

from ehf.domain.gender import GENDERS
from ehf.domain.goal_distribution import format_int, format_share
from ehf.domain.matches import Choice

if TYPE_CHECKING:
    from ehf.domain.attendance_calendar import CalendarReport
    from ehf.domain.attendance_cities import CityReport
    from ehf.domain.attendance_extended_records import ExtendedRecords
    from ehf.domain.attendance_opponents import OpponentSection
    from ehf.domain.attendance_science import ScienceReport

RECORD_LIMIT = 50
CLUB_RANKING_LIMIT = 100
MOVING_AVERAGE_WINDOW = 3
COMPLETENESS_NOTE = "Matches without known attendance are excluded from averages."
NO_CAPACITY_NOTE = "Venue capacity is not available, so fill rate is not shown."


def format_signed_percent(change: float | None) -> str:
    if change is None:
        return "—"
    return f"{change * 100:+.1f}%"


def format_signed_decimal(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:+,.0f}".replace(",", " ")


def format_optional_int(value: int | None) -> str:
    if value is None:
        return "—"
    return format_int(value)


def format_rounded(value: float | None) -> str:
    if value is None:
        return "—"
    return format_int(round(value))


@dataclass(frozen=True)
class AttendanceFilters:
    season_id: int | None = None
    competition_id: int | None = None
    gender: str | None = None
    phase: str | None = None
    club_id: int | None = None
    exclude_zeros: bool = False
    date_from: date | None = None
    date_to: date | None = None

    def __post_init__(self) -> None:
        if self.gender is not None and self.gender not in GENDERS:
            raise ValueError("gender must be men or women")
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not be after date_to")

    @property
    def has_date_range(self) -> bool:
        return self.date_from is not None or self.date_to is not None

    def without_season(self) -> AttendanceFilters:
        return replace(self, season_id=None)


@dataclass(frozen=True)
class AttendanceFilterChoices:
    seasons: tuple[Choice, ...]
    competitions: tuple[Choice, ...]
    phases: tuple[Choice, ...]
    clubs: tuple[Choice, ...]


@dataclass(frozen=True)
class AttendanceSummary:
    played: int
    known: int
    total: int
    mean: float | None
    median: float | None
    q1: float | None
    q3: float | None
    minimum: int | None
    maximum: int | None
    zero_matches: int = 0

    def __post_init__(self) -> None:
        if self.played < 0 or self.known < 0 or self.zero_matches < 0:
            raise ValueError("match counts cannot be negative")
        if self.known > self.played:
            raise ValueError("known matches cannot exceed played matches")

    @property
    def excluded(self) -> int:
        return self.played - self.known

    @property
    def coverage(self) -> float | None:
        if self.played == 0:
            return None
        return self.known / self.played

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
    def coverage_label(self) -> str:
        if self.coverage is None:
            return "—"
        return format_share(self.coverage)

    @property
    def mean_label(self) -> str:
        return format_rounded(self.mean)

    @property
    def median_label(self) -> str:
        return format_rounded(self.median)

    @property
    def q1_label(self) -> str:
        return format_rounded(self.q1)

    @property
    def q3_label(self) -> str:
        return format_rounded(self.q3)

    @property
    def minimum_label(self) -> str:
        return format_optional_int(self.minimum)

    @property
    def maximum_label(self) -> str:
        return format_optional_int(self.maximum)


@dataclass(frozen=True)
class SeasonAttendance:
    season_id: int
    season_code: str
    year_start: int
    summary: AttendanceSummary


@dataclass(frozen=True)
class TrendPoint:
    season: SeasonAttendance
    yoy: float | None
    moving_average: float | None

    @property
    def yoy_label(self) -> str:
        return format_signed_percent(self.yoy)

    @property
    def moving_average_label(self) -> str:
        return format_rounded(self.moving_average)


@dataclass(frozen=True)
class AttendanceTrend:
    points: tuple[TrendPoint, ...]
    slope: float | None

    @property
    def slope_label(self) -> str:
        if self.slope is None:
            return "—"
        return f"{format_signed_decimal(self.slope)} per season"


@dataclass(frozen=True)
class SeasonPair:
    target: TrendPoint
    previous: TrendPoint

    @property
    def change(self) -> float | None:
        return AttendanceStatsCalculator.yoy_change(
            self.target.season.summary.mean, self.previous.season.summary.mean
        )

    @property
    def change_label(self) -> str:
        return format_signed_percent(self.change)

    @property
    def caption(self) -> str:
        return f"{self.target.season.season_code} vs {self.previous.season.season_code}"


@dataclass(frozen=True)
class MatchAttendanceRecord:
    home_club_id: int | None
    home_club_name: str
    away_club_id: int | None
    away_club_name: str
    spectators: int | None


@dataclass(frozen=True)
class ClubAttendance:
    club_id: int
    club_name: str
    summary: AttendanceSummary


@dataclass(frozen=True)
class ClubSeasonMean:
    club_id: int
    season_id: int
    mean: float


@dataclass(frozen=True)
class ClubRankingRow:
    position: int
    club: ClubAttendance
    yoy: float | None

    @property
    def yoy_label(self) -> str:
        return format_signed_percent(self.yoy)


@dataclass(frozen=True)
class AttendanceRecord:
    match_id: int
    kickoff: datetime | None
    season: str
    competition: str
    home: str
    away: str
    home_goals: int | None
    away_goals: int | None
    venue: str | None
    spectators: int

    @property
    def kickoff_label(self) -> str:
        if self.kickoff is None:
            return "—"
        return self.kickoff.strftime("%Y-%m-%d")

    @property
    def score_label(self) -> str:
        if self.home_goals is None or self.away_goals is None:
            return "—"
        return f"{self.home_goals}:{self.away_goals}"

    @property
    def venue_label(self) -> str:
        return self.venue or "—"

    @property
    def spectators_label(self) -> str:
        return format_int(self.spectators)


@dataclass(frozen=True)
class AttendanceReport:
    filters: AttendanceFilters
    summary: AttendanceSummary
    trend: AttendanceTrend
    season_pair: SeasonPair | None
    ranking: tuple[ClubRankingRow, ...]
    records: tuple[AttendanceRecord, ...]
    opponents: OpponentSection | None = None
    calendar: CalendarReport | None = None
    extended_records: ExtendedRecords | None = None
    science: ScienceReport | None = None
    cities: CityReport | None = None

    @property
    def record(self) -> AttendanceRecord | None:
        return self.records[0] if self.records else None

    @property
    def yoy_label(self) -> str:
        if self.season_pair is None:
            return "—"
        return self.season_pair.change_label

    @property
    def yoy_caption(self) -> str:
        if self.season_pair is None:
            return "No comparable previous season"
        return f"Mean, {self.season_pair.caption}"

    @property
    def completeness_notes(self) -> tuple[str, ...]:
        summary = self.summary
        notes = [
            COMPLETENESS_NOTE,
            f"Known attendance: {summary.known_label} of {summary.played_label} played matches "
            f"({summary.coverage_label}).",
        ]
        if summary.zero_matches:
            count = format_int(summary.zero_matches)
            if self.filters.exclude_zeros:
                notes.append(f"{count} matches with 0 spectators are excluded by the filter.")
            else:
                notes.append(f"{count} matches with 0 spectators are counted as known closed-doors matches.")
        notes.append(NO_CAPACITY_NOTE)
        return tuple(notes)


class AttendanceStatsCalculator:
    @staticmethod
    def known_values(
        values: Sequence[int | None], exclude_zeros: bool = False
    ) -> tuple[int, ...]:
        return tuple(
            value
            for value in values
            if value is not None and value >= 0 and not (exclude_zeros and value == 0)
        )

    @staticmethod
    def mean(values: Sequence[float]) -> float | None:
        if not values:
            return None
        return sum(values) / len(values)

    @staticmethod
    def percentile(values: Sequence[float], fraction: float) -> float | None:
        if not values:
            return None
        if not 0 <= fraction <= 1:
            raise ValueError("fraction must be between 0 and 1")
        ordered = sorted(values)
        position = fraction * (len(ordered) - 1)
        lower = math.floor(position)
        upper = math.ceil(position)
        if lower == upper:
            return float(ordered[lower])
        weight = position - lower
        return ordered[lower] + (ordered[upper] - ordered[lower]) * weight

    @staticmethod
    def median(values: Sequence[float]) -> float | None:
        return AttendanceStatsCalculator.percentile(values, 0.5)

    @staticmethod
    def quartiles(values: Sequence[float]) -> tuple[float | None, float | None]:
        return (
            AttendanceStatsCalculator.percentile(values, 0.25),
            AttendanceStatsCalculator.percentile(values, 0.75),
        )

    @staticmethod
    def summarize(
        values: Sequence[int | None], exclude_zeros: bool = False
    ) -> AttendanceSummary:
        known = AttendanceStatsCalculator.known_values(values, exclude_zeros)
        q1, q3 = AttendanceStatsCalculator.quartiles(known)
        return AttendanceSummary(
            played=len(values),
            known=len(known),
            total=sum(known),
            mean=AttendanceStatsCalculator.mean(known),
            median=AttendanceStatsCalculator.median(known),
            q1=q1,
            q3=q3,
            minimum=min(known) if known else None,
            maximum=max(known) if known else None,
            zero_matches=sum(1 for value in values if value == 0),
        )

    @staticmethod
    def yoy_change(current: float | None, previous: float | None) -> float | None:
        if current is None or previous is None or previous == 0:
            return None
        return (current - previous) / previous

    @staticmethod
    def moving_average(
        values: Sequence[float | None], window: int = MOVING_AVERAGE_WINDOW
    ) -> tuple[float | None, ...]:
        if window < 1:
            raise ValueError("window must be positive")
        averaged: list[float | None] = []
        for index, value in enumerate(values):
            if value is None:
                averaged.append(None)
                continue
            start = max(0, index - window + 1)
            recent = [item for item in values[start : index + 1] if item is not None]
            averaged.append(sum(recent) / len(recent))
        return tuple(averaged)

    @staticmethod
    def linear_slope(points: Sequence[tuple[float, float | None]]) -> float | None:
        known = [(x, y) for x, y in points if y is not None]
        if len(known) < 2:
            return None
        mean_x = sum(x for x, _ in known) / len(known)
        mean_y = sum(y for _, y in known) / len(known)
        variance = sum((x - mean_x) ** 2 for x, _ in known)
        if variance == 0:
            return None
        covariance = sum((x - mean_x) * (y - mean_y) for x, y in known)
        return covariance / variance

    @staticmethod
    def build_trend(seasons: Sequence[SeasonAttendance]) -> AttendanceTrend:
        ordered = sorted(seasons, key=lambda season: season.year_start)
        means = [season.summary.mean for season in ordered]
        averages = AttendanceStatsCalculator.moving_average(means)
        points = tuple(
            TrendPoint(
                season=season,
                yoy=AttendanceStatsCalculator.yoy_change(
                    means[index], means[index - 1] if index else None
                ),
                moving_average=averages[index],
            )
            for index, season in enumerate(ordered)
        )
        slope = AttendanceStatsCalculator.linear_slope(
            [(float(season.year_start), mean) for season, mean in zip(ordered, means)]
        )
        return AttendanceTrend(points=points, slope=slope)

    @staticmethod
    def comparison_pair(
        trend: AttendanceTrend, selected_season_id: int | None
    ) -> SeasonPair | None:
        points = trend.points
        target_index = AttendanceStatsCalculator._target_index(points, selected_season_id)
        if target_index is None or target_index == 0:
            return None
        target, previous = points[target_index], points[target_index - 1]
        if target.season.summary.mean is None or previous.season.summary.mean is None:
            return None
        return SeasonPair(target=target, previous=previous)

    @staticmethod
    def _target_index(
        points: Sequence[TrendPoint], selected_season_id: int | None
    ) -> int | None:
        if selected_season_id is not None:
            for index, point in enumerate(points):
                if point.season.season_id == selected_season_id:
                    return index
            return None
        for index in range(len(points) - 1, -1, -1):
            if points[index].season.summary.mean is not None:
                return index
        return None

    @staticmethod
    def aggregate_home_clubs(
        records: Sequence[MatchAttendanceRecord], exclude_zeros: bool = False
    ) -> tuple[ClubAttendance, ...]:
        grouped: dict[int, list[MatchAttendanceRecord]] = {}
        for record in records:
            if record.home_club_id is None:
                continue
            grouped.setdefault(record.home_club_id, []).append(record)
        return tuple(
            ClubAttendance(
                club_id=club_id,
                club_name=matches[-1].home_club_name,
                summary=AttendanceStatsCalculator.summarize(
                    [match.spectators for match in matches], exclude_zeros
                ),
            )
            for club_id, matches in grouped.items()
        )

    @staticmethod
    def rank_clubs(
        clubs: Sequence[ClubAttendance],
        season_means: Sequence[ClubSeasonMean],
        pair: SeasonPair | None,
        limit: int = CLUB_RANKING_LIMIT,
    ) -> tuple[ClubRankingRow, ...]:
        means: Mapping[tuple[int, int], float] = {
            (item.club_id, item.season_id): item.mean for item in season_means
        }
        eligible = [club for club in clubs if club.summary.mean is not None]
        eligible.sort(
            key=lambda club: (
                -(club.summary.mean or 0.0),
                -club.summary.known,
                club.club_name.casefold(),
                club.club_id,
            )
        )
        return tuple(
            ClubRankingRow(
                position=position,
                club=club,
                yoy=AttendanceStatsCalculator._club_yoy(club.club_id, means, pair),
            )
            for position, club in enumerate(eligible[:limit], start=1)
        )

    @staticmethod
    def _club_yoy(
        club_id: int, means: Mapping[tuple[int, int], float], pair: SeasonPair | None
    ) -> float | None:
        if pair is None:
            return None
        return AttendanceStatsCalculator.yoy_change(
            means.get((club_id, pair.target.season.season_id)),
            means.get((club_id, pair.previous.season.season_id)),
        )
