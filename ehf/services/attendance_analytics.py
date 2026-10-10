from __future__ import annotations

from typing import Protocol

from ehf.domain.attendance_analytics import (
    CLUB_RANKING_LIMIT,
    RECORD_LIMIT,
    AttendanceFilterChoices,
    AttendanceFilters,
    AttendanceRecord,
    AttendanceReport,
    AttendanceStatsCalculator,
    AttendanceSummary,
    ClubAttendance,
    ClubSeasonMean,
    SeasonAttendance,
)
from ehf.domain.attendance_calendar import CalendarCalculator, CalendarCell, CalendarReport
from ehf.domain.attendance_cities import (
    CITY_LIMIT,
    CONTRIBUTION_LIMIT,
    CityBundle,
    CityCalculator,
    CityReport,
)
from ehf.domain.attendance_extended_records import ExtendedRecords
from ehf.domain.attendance_opponents import (
    OPPONENT_LIMIT,
    OpponentAttendance,
    OpponentCalculator,
    OpponentSection,
)
from ehf.domain.attendance_science import (
    SAMPLE_LIMIT,
    AttendanceScienceCalculator,
    MatchSample,
    ScienceReport,
)
from ehf.domain.matches import Choice

ATTENDANCE_GENDERS = (
    Choice("men", "Men"),
    Choice("women", "Women"),
)


class AttendanceReader(Protocol):
    def fetch_choices(self) -> AttendanceFilterChoices: ...

    def fetch_summary(self, filters: AttendanceFilters) -> AttendanceSummary: ...

    def fetch_season_summaries(
        self, filters: AttendanceFilters
    ) -> tuple[SeasonAttendance, ...]: ...

    def fetch_club_attendance(
        self, filters: AttendanceFilters
    ) -> tuple[ClubAttendance, ...]: ...

    def fetch_club_season_means(
        self, filters: AttendanceFilters
    ) -> tuple[ClubSeasonMean, ...]: ...

    def fetch_top_matches(
        self, filters: AttendanceFilters, limit: int
    ) -> tuple[AttendanceRecord, ...]: ...


class OpponentReader(Protocol):
    def fetch_opponents(
        self, filters: AttendanceFilters, limit: int
    ) -> tuple[OpponentAttendance, ...]: ...


class CalendarReader(Protocol):
    def fetch_calendar(self, filters: AttendanceFilters) -> tuple[CalendarCell, ...]: ...


class CityReader(Protocol):
    def fetch_city_bundle(
        self, filters: AttendanceFilters, city_limit: int, contribution_limit: int
    ) -> CityBundle: ...


class ExtendedRecordReader(Protocol):
    def fetch_extended_records(self, filters: AttendanceFilters) -> ExtendedRecords: ...


class MatchSampleReader(Protocol):
    def fetch_match_sample(
        self, filters: AttendanceFilters, limit: int
    ) -> tuple[MatchSample, ...]: ...


class AttendanceAnalyticsReader(
    AttendanceReader,
    OpponentReader,
    CalendarReader,
    CityReader,
    ExtendedRecordReader,
    MatchSampleReader,
    Protocol,
): ...


class AttendanceAnalyticsService:
    def __init__(self, reader: AttendanceAnalyticsReader) -> None:
        self._reader = reader

    def choices(self) -> AttendanceFilterChoices:
        return self._reader.fetch_choices()

    def genders(self) -> tuple[Choice, ...]:
        return ATTENDANCE_GENDERS

    def report(self, filters: AttendanceFilters) -> AttendanceReport:
        summary = self._reader.fetch_summary(filters)
        trend = AttendanceStatsCalculator.build_trend(
            self._reader.fetch_season_summaries(filters)
        )
        pair = (
            None
            if filters.has_date_range
            else AttendanceStatsCalculator.comparison_pair(trend, filters.season_id)
        )
        season_means = (
            self._reader.fetch_club_season_means(filters) if pair is not None else ()
        )
        ranking = AttendanceStatsCalculator.rank_clubs(
            self._reader.fetch_club_attendance(filters),
            season_means,
            pair,
            CLUB_RANKING_LIMIT,
        )
        return AttendanceReport(
            filters=filters,
            summary=summary,
            trend=trend,
            season_pair=pair,
            ranking=ranking,
            records=self._reader.fetch_top_matches(filters, RECORD_LIMIT),
            opponents=self._opponents(filters, summary),
            calendar=self._calendar(filters),
            cities=self._cities(filters),
            extended_records=self._reader.fetch_extended_records(filters),
            science=self._science(filters, summary),
        )

    def _opponents(
        self, filters: AttendanceFilters, summary: AttendanceSummary
    ) -> OpponentSection:
        if filters.club_id is None:
            return OpponentSection.club_required()
        return OpponentCalculator.build_section(
            filters.club_id,
            self._reader.fetch_opponents(filters, OPPONENT_LIMIT),
            summary.mean,
            OPPONENT_LIMIT,
        )

    def _calendar(self, filters: AttendanceFilters) -> CalendarReport:
        return CalendarCalculator.build(self._reader.fetch_calendar(filters))

    def _cities(self, filters: AttendanceFilters) -> CityReport:
        bundle = self._reader.fetch_city_bundle(filters, CITY_LIMIT, CONTRIBUTION_LIMIT)
        return CityCalculator.build(bundle, CITY_LIMIT, CONTRIBUTION_LIMIT)

    def _science(
        self, filters: AttendanceFilters, summary: AttendanceSummary
    ) -> ScienceReport:
        sample = self._reader.fetch_match_sample(filters, SAMPLE_LIMIT)
        return AttendanceScienceCalculator.build(sample, summary.known, filters.club_id)
