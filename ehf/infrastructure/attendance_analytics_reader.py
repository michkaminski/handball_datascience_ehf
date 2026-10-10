from __future__ import annotations

from collections.abc import Callable, Sequence

from psycopg import Connection, Error
from psycopg.rows import dict_row

from ehf.domain.attendance_analytics import (
    AttendanceFilterChoices,
    AttendanceFilters,
    AttendanceRecord,
    AttendanceSummary,
    ClubAttendance,
    ClubSeasonMean,
    SeasonAttendance,
)
from ehf.domain.attendance_calendar import CalendarCell
from ehf.domain.attendance_cities import CityBundle
from ehf.domain.attendance_extended_records import ExtendedRecords
from ehf.domain.attendance_opponents import OpponentAttendance
from ehf.domain.attendance_science import MatchSample
from ehf.domain.errors import DataReadError
from ehf.domain.matches import Choice
from ehf.infrastructure.attendance_cities_queries import (
    city_contributions_sql,
    city_from_row,
    cities_sql,
    contribution_from_row,
    matches_without_city_sql,
)
from ehf.infrastructure.attendance_city_breakdown_queries import (
    city_competitions_sql,
    city_seasons_sql,
    city_venues_sql,
    competition_from_row,
    season_from_row,
    venue_from_row,
)
from ehf.infrastructure.attendance_extended_queries import (
    RECORD_SPECS,
    calendar_cell_from_row,
    calendar_sql,
    opponent_from_row,
    opponents_sql,
    record_from_row,
    record_sql,
)
from ehf.infrastructure.attendance_sample_query import sample_from_row, sample_sql
from ehf.infrastructure.kickoff import KICKOFF_AT_SQL
from ehf.infrastructure.played import (
    AWAY_NAME,
    EDITION_JOINS,
    HOME_NAME,
    PLAYED_SQL,
    SCORE_AWAY,
    SCORE_HOME,
    TEAM_JOINS,
)

KNOWN_SQL = "m.spectators >= 0"
KNOWN_NONZERO_SQL = "m.spectators > 0"

SEASONS_SQL = """
SELECT id::text AS value, code AS label
FROM ehf.season
ORDER BY year_start DESC
"""

COMPETITIONS_SQL = """
SELECT id::text AS value, name AS label
FROM ehf.competition
ORDER BY name
"""

PHASES_SQL = """
SELECT DISTINCT phase AS value, phase AS label
FROM ehf.match
WHERE phase IS NOT NULL AND btrim(phase) <> ''
ORDER BY phase
"""

CLUBS_SQL = """
SELECT
    ed.club_id::text AS value,
    (ARRAY_AGG(ed.display_name ORDER BY s.year_start DESC))[1] AS label
FROM ehf.club_edition ed
JOIN ehf.competition_edition ce ON ce.id = ed.competition_edition_id
JOIN ehf.season s ON s.id = ce.season_id
GROUP BY ed.club_id
ORDER BY label
"""


def known_predicate(filters: AttendanceFilters) -> str:
    return KNOWN_NONZERO_SQL if filters.exclude_zeros else KNOWN_SQL


def aggregate_columns(known: str) -> str:
    return f"""
    COUNT(*)::int AS played,
    (COUNT(*) FILTER (WHERE {known}))::int AS known,
    COALESCE((SUM(m.spectators) FILTER (WHERE {known})), 0)::bigint AS total,
    (AVG(m.spectators) FILTER (WHERE {known}))::float8 AS mean,
    (percentile_cont(0.5) WITHIN GROUP (ORDER BY m.spectators) FILTER (WHERE {known}))::float8 AS median,
    (percentile_cont(0.25) WITHIN GROUP (ORDER BY m.spectators) FILTER (WHERE {known}))::float8 AS q1,
    (percentile_cont(0.75) WITHIN GROUP (ORDER BY m.spectators) FILTER (WHERE {known}))::float8 AS q3,
    (MIN(m.spectators) FILTER (WHERE {known}))::int AS minimum,
    (MAX(m.spectators) FILTER (WHERE {known}))::int AS maximum,
    (COUNT(*) FILTER (WHERE m.spectators = 0))::int AS zero_matches
"""


def build_where(
    filters: AttendanceFilters, *, with_season: bool = True
) -> tuple[str, list[object]]:
    clauses = [PLAYED_SQL]
    params: list[object] = []
    if with_season and filters.season_id is not None:
        clauses.append("s.id = %s")
        params.append(filters.season_id)
    if filters.competition_id is not None:
        clauses.append("c.id = %s")
        params.append(filters.competition_id)
    if filters.gender is not None:
        clauses.append("c.gender = %s")
        params.append(filters.gender)
    if filters.phase is not None:
        clauses.append("m.phase = %s")
        params.append(filters.phase)
    if filters.club_id is not None:
        clauses.append("m.home_club_id = %s")
        params.append(filters.club_id)
    if filters.date_from is not None:
        clauses.append(f"{KICKOFF_AT_SQL}::date >= %s")
        params.append(filters.date_from)
    if filters.date_to is not None:
        clauses.append(f"{KICKOFF_AT_SQL}::date <= %s")
        params.append(filters.date_to)
    return " AND ".join(clauses), params


def summary_sql(filters: AttendanceFilters) -> tuple[str, list[object]]:
    where, params = build_where(filters)
    sql = f"""
SELECT {aggregate_columns(known_predicate(filters))}
FROM ehf.match m
{EDITION_JOINS}
WHERE {where}
"""
    return sql, params


def seasons_sql(filters: AttendanceFilters) -> tuple[str, list[object]]:
    where, params = build_where(filters, with_season=False)
    sql = f"""
SELECT
    s.id AS season_id,
    s.code AS season_code,
    s.year_start,
    {aggregate_columns(known_predicate(filters))}
FROM ehf.match m
{EDITION_JOINS}
WHERE {where}
GROUP BY s.id, s.code, s.year_start
ORDER BY s.year_start
"""
    return sql, params


def clubs_sql(filters: AttendanceFilters) -> tuple[str, list[object]]:
    where, params = build_where(filters)
    known = known_predicate(filters)
    sql = f"""
SELECT
    m.home_club_id AS club_id,
    COALESCE(
        (ARRAY_AGG(NULLIF(btrim({HOME_NAME}), '') ORDER BY s.year_start DESC)
            FILTER (WHERE NULLIF(btrim({HOME_NAME}), '') IS NOT NULL))[1],
        '—'
    ) AS club_name,
    {aggregate_columns(known)}
FROM ehf.match m
{EDITION_JOINS}
{TEAM_JOINS}
WHERE {where} AND m.home_club_id IS NOT NULL
GROUP BY m.home_club_id
HAVING COUNT(*) FILTER (WHERE {known}) > 0
"""
    return sql, params


def club_season_means_sql(filters: AttendanceFilters) -> tuple[str, list[object]]:
    where, params = build_where(filters, with_season=False)
    known = known_predicate(filters)
    sql = f"""
SELECT
    m.home_club_id AS club_id,
    s.id AS season_id,
    (AVG(m.spectators) FILTER (WHERE {known}))::float8 AS mean
FROM ehf.match m
{EDITION_JOINS}
WHERE {where} AND m.home_club_id IS NOT NULL
GROUP BY m.home_club_id, s.id
HAVING COUNT(*) FILTER (WHERE {known}) > 0
"""
    return sql, params


def top_matches_sql(filters: AttendanceFilters, limit: int) -> tuple[str, list[object]]:
    where, params = build_where(filters)
    sql = f"""
SELECT
    m.id,
    {KICKOFF_AT_SQL} AS kickoff_at,
    s.code AS season_code,
    COALESCE(NULLIF(btrim(c.name), ''), '—') AS competition_name,
    COALESCE(NULLIF(btrim({HOME_NAME}), ''), '—') AS home_name,
    COALESCE(NULLIF(btrim({AWAY_NAME}), ''), '—') AS away_name,
    {SCORE_HOME} AS score_home,
    {SCORE_AWAY} AS score_away,
    NULLIF(CONCAT_WS(', ', v.name, v.city), '') AS venue_name,
    m.spectators
FROM ehf.match m
{EDITION_JOINS}
{TEAM_JOINS}
LEFT JOIN ehf.venue v ON v.id = m.venue_id
WHERE {where} AND {known_predicate(filters)}
ORDER BY m.spectators DESC, kickoff_at DESC NULLS LAST, m.id DESC
LIMIT %s
"""
    return sql, [*params, limit]


def summary_from_row(row: dict) -> AttendanceSummary:
    return AttendanceSummary(
        played=int(row["played"]),
        known=int(row["known"]),
        total=int(row["total"]),
        mean=row["mean"],
        median=row["median"],
        q1=row["q1"],
        q3=row["q3"],
        minimum=row["minimum"],
        maximum=row["maximum"],
        zero_matches=int(row["zero_matches"]),
    )


class PsycopgAttendanceAnalyticsReader:
    def __init__(self, connect: Callable[[], Connection]) -> None:
        self._connect = connect

    def fetch_choices(self) -> AttendanceFilterChoices:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    return AttendanceFilterChoices(
                        seasons=self._choices(cursor, SEASONS_SQL),
                        competitions=self._choices(cursor, COMPETITIONS_SQL),
                        phases=self._choices(cursor, PHASES_SQL),
                        clubs=self._choices(cursor, CLUBS_SQL),
                    )
        except Error as exc:
            raise DataReadError(f"Could not read attendance filters: {exc}") from exc

    def fetch_summary(self, filters: AttendanceFilters) -> AttendanceSummary:
        rows = self._rows(summary_sql(filters), "attendance summary")
        return summary_from_row(rows[0])

    def fetch_season_summaries(
        self, filters: AttendanceFilters
    ) -> tuple[SeasonAttendance, ...]:
        rows = self._rows(seasons_sql(filters), "seasonal attendance")
        return tuple(
            SeasonAttendance(
                season_id=int(row["season_id"]),
                season_code=str(row["season_code"]),
                year_start=int(row["year_start"]),
                summary=summary_from_row(row),
            )
            for row in rows
        )

    def fetch_club_attendance(
        self, filters: AttendanceFilters
    ) -> tuple[ClubAttendance, ...]:
        rows = self._rows(clubs_sql(filters), "home club attendance")
        return tuple(
            ClubAttendance(
                club_id=int(row["club_id"]),
                club_name=str(row["club_name"]),
                summary=summary_from_row(row),
            )
            for row in rows
        )

    def fetch_club_season_means(
        self, filters: AttendanceFilters
    ) -> tuple[ClubSeasonMean, ...]:
        rows = self._rows(club_season_means_sql(filters), "club season attendance")
        return tuple(
            ClubSeasonMean(int(row["club_id"]), int(row["season_id"]), float(row["mean"]))
            for row in rows
        )

    def fetch_top_matches(
        self, filters: AttendanceFilters, limit: int
    ) -> tuple[AttendanceRecord, ...]:
        rows = self._rows(top_matches_sql(filters, limit), "attendance records")
        return tuple(record_from_row(row) for row in rows)

    def fetch_opponents(
        self, filters: AttendanceFilters, limit: int
    ) -> tuple[OpponentAttendance, ...]:
        if filters.club_id is None:
            return ()
        where, params = build_where(filters)
        query = opponents_sql(where, params, known_predicate(filters), limit)
        return tuple(opponent_from_row(row) for row in self._rows(query, "opponent attendance"))

    def fetch_calendar(self, filters: AttendanceFilters) -> tuple[CalendarCell, ...]:
        where, params = build_where(filters)
        query = calendar_sql(where, params, known_predicate(filters))
        return tuple(calendar_cell_from_row(row) for row in self._rows(query, "calendar attendance"))

    def fetch_city_bundle(
        self, filters: AttendanceFilters, city_limit: int, contribution_limit: int
    ) -> CityBundle:
        where, params = build_where(filters)
        known = known_predicate(filters)
        (
            city_rows,
            contribution_rows,
            season_rows,
            competition_rows,
            venue_rows,
            missing_rows,
        ) = self._rows_many(
            [
                cities_sql(where, params, known, city_limit),
                city_contributions_sql(where, params, known, contribution_limit),
                city_seasons_sql(where, params, known, city_limit),
                city_competitions_sql(where, params, known, city_limit),
                city_venues_sql(where, params, known, city_limit),
                matches_without_city_sql(where, params),
            ],
            "city attendance",
        )
        return CityBundle(
            cities=tuple(city_from_row(row) for row in city_rows),
            contributions=tuple(contribution_from_row(row) for row in contribution_rows),
            seasons=tuple(season_from_row(row) for row in season_rows),
            competitions=tuple(competition_from_row(row) for row in competition_rows),
            venues=tuple(venue_from_row(row) for row in venue_rows),
            matches_without_city=int(missing_rows[0]["missing"]),
        )

    def fetch_extended_records(self, filters: AttendanceFilters) -> ExtendedRecords:
        known = known_predicate(filters)
        queries = []
        for spec in RECORD_SPECS:
            where, params = build_where(filters, with_season=spec.with_season)
            queries.append(record_sql(spec, where, params, known))
        results = self._rows_many(queries, "extended attendance records")
        return ExtendedRecords(
            **{
                spec.name: tuple(record_from_row(row) for row in rows)
                for spec, rows in zip(RECORD_SPECS, results)
            }
        )

    def fetch_match_sample(
        self, filters: AttendanceFilters, limit: int
    ) -> tuple[MatchSample, ...]:
        where, params = build_where(filters)
        query = sample_sql(where, params, known_predicate(filters), limit)
        rows = self._rows(query, "attendance match sample")
        return tuple(sample_from_row(row) for row in reversed(rows))

    def _rows(self, query: tuple[str, list[object]], subject: str) -> list[dict]:
        return self._rows_many([query], subject)[0]

    def _rows_many(
        self, queries: Sequence[tuple[str, list[object]]], subject: str
    ) -> list[list[dict]]:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    results = []
                    for sql, params in queries:
                        cursor.execute(sql, params)
                        results.append(cursor.fetchall())
                    return results
        except Error as exc:
            raise DataReadError(f"Could not read {subject}: {exc}") from exc

    def _choices(self, cursor, sql: str) -> tuple[Choice, ...]:
        cursor.execute(sql)
        return tuple(Choice(value=row["value"], label=row["label"]) for row in cursor.fetchall())
