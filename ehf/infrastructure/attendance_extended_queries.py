from __future__ import annotations

from dataclasses import dataclass

from ehf.domain.attendance_analytics import AttendanceRecord
from ehf.domain.attendance_calendar import (
    DAY_TYPE_WEEKDAY,
    DAY_TYPE_WEEKEND,
    DIMENSION_DAY_TYPE,
    DIMENSION_HEATMAP,
    DIMENSION_HOUR,
    DIMENSION_MONTH,
    DIMENSION_PHASE,
    DIMENSION_WEEKDAY,
    CalendarCell,
)
from ehf.domain.attendance_extended_records import EXTENDED_RECORD_LIMIT, FINALS_PATTERN
from ehf.domain.attendance_opponents import OpponentAttendance
from ehf.infrastructure.kickoff import KICKOFF_AT_SQL
from ehf.infrastructure.played import (
    AWAY_NAME,
    EDITION_JOINS,
    HOME_NAME,
    SCORE_AWAY,
    SCORE_HOME,
    TEAM_JOINS,
)

WEEKDAY_SQL = "(EXTRACT(ISODOW FROM kickoff_at)::int - 1)::text"
HOUR_SQL = "EXTRACT(HOUR FROM kickoff_at)::int::text"
HAS_KICKOFF_SQL = "kickoff_at IS NOT NULL"


@dataclass(frozen=True)
class CalendarDimensionSpec:
    name: str
    primary: str
    secondary: str | None = None
    condition: str = HAS_KICKOFF_SQL


CALENDAR_DIMENSIONS = (
    CalendarDimensionSpec(DIMENSION_MONTH, "EXTRACT(MONTH FROM kickoff_at)::int::text"),
    CalendarDimensionSpec(DIMENSION_WEEKDAY, WEEKDAY_SQL),
    CalendarDimensionSpec(DIMENSION_HOUR, HOUR_SQL),
    CalendarDimensionSpec(
        DIMENSION_DAY_TYPE,
        f"CASE WHEN EXTRACT(ISODOW FROM kickoff_at) >= 6 "
        f"THEN '{DAY_TYPE_WEEKEND}' ELSE '{DAY_TYPE_WEEKDAY}' END",
    ),
    CalendarDimensionSpec(
        DIMENSION_PHASE, "COALESCE(NULLIF(btrim(m.phase), ''), '')", condition="TRUE"
    ),
    CalendarDimensionSpec(DIMENSION_HEATMAP, WEEKDAY_SQL, HOUR_SQL),
)


@dataclass(frozen=True)
class RecordSpec:
    name: str
    partition: str | None
    extra_where: str
    extra_params: tuple[object, ...]
    outer_order: str
    limit: int | None
    with_season: bool = True


RECORD_ORDER = "spectators DESC, kickoff_at DESC NULLS LAST, id DESC"
RECORD_SPECS = (
    RecordSpec("seasons", "s.id", "", (), "season_year DESC", None, with_season=False),
    RecordSpec(
        "clubs",
        "m.home_club_id",
        "AND m.home_club_id IS NOT NULL",
        (),
        RECORD_ORDER,
        EXTENDED_RECORD_LIMIT,
    ),
    RecordSpec(
        "venues",
        "m.venue_id",
        "AND m.venue_id IS NOT NULL",
        (),
        RECORD_ORDER,
        EXTENDED_RECORD_LIMIT,
    ),
    RecordSpec(
        "finals",
        None,
        "AND m.phase ILIKE %s",
        (FINALS_PATTERN,),
        RECORD_ORDER,
        EXTENDED_RECORD_LIMIT,
    ),
    RecordSpec(
        "rivalries",
        "m.home_club_id, m.away_club_id",
        "AND m.home_club_id IS NOT NULL AND m.away_club_id IS NOT NULL",
        (),
        RECORD_ORDER,
        EXTENDED_RECORD_LIMIT,
    ),
)

RECORD_COLUMNS = f"""
    m.id,
    {KICKOFF_AT_SQL} AS kickoff_at,
    s.year_start AS season_year,
    s.code AS season_code,
    COALESCE(NULLIF(btrim(c.name), ''), '—') AS competition_name,
    COALESCE(NULLIF(btrim({HOME_NAME}), ''), '—') AS home_name,
    COALESCE(NULLIF(btrim({AWAY_NAME}), ''), '—') AS away_name,
    {SCORE_HOME} AS score_home,
    {SCORE_AWAY} AS score_away,
    NULLIF(CONCAT_WS(', ', v.name, v.city), '') AS venue_name,
    m.spectators
"""
RECORD_SOURCE = f"""
FROM ehf.match m
{EDITION_JOINS}
{TEAM_JOINS}
LEFT JOIN ehf.venue v ON v.id = m.venue_id
"""


def opponents_sql(
    where: str, params: list[object], known: str, limit: int
) -> tuple[str, list[object]]:
    name = f"NULLIF(btrim({AWAY_NAME}), '')"
    sql = f"""
SELECT
    m.away_club_id AS opponent_id,
    COALESCE((ARRAY_AGG({name} ORDER BY s.year_start DESC) FILTER (WHERE {name} IS NOT NULL))[1], '—')
        AS opponent_name,
    COUNT(*)::int AS played,
    (COUNT(*) FILTER (WHERE {known}))::int AS known,
    (AVG(m.spectators) FILTER (WHERE {known}))::float8 AS mean,
    (MAX(m.spectators) FILTER (WHERE {known}))::int AS maximum
FROM ehf.match m
{EDITION_JOINS}
{TEAM_JOINS}
WHERE {where} AND m.away_club_id IS NOT NULL
GROUP BY m.away_club_id
HAVING COUNT(*) FILTER (WHERE {known}) > 0
ORDER BY mean DESC, known DESC, opponent_name
LIMIT %s
"""
    return sql, [*params, limit]


def opponent_from_row(row: dict) -> OpponentAttendance:
    return OpponentAttendance(
        opponent_id=int(row["opponent_id"]),
        opponent_name=str(row["opponent_name"]),
        played=int(row["played"]),
        known=int(row["known"]),
        mean=row["mean"],
        maximum=row["maximum"],
    )


def calendar_select(spec: CalendarDimensionSpec, known: str) -> str:
    secondary = spec.secondary or "NULL::text"
    group = "GROUP BY 2, 3" if spec.secondary else "GROUP BY 2"
    return f"""
SELECT
    '{spec.name}' AS dimension,
    {spec.primary} AS key_a,
    {secondary} AS key_b,
    COUNT(*)::int AS played,
    (COUNT(*) FILTER (WHERE {known}))::int AS known,
    (AVG(m.spectators) FILTER (WHERE {known}))::float8 AS mean
FROM base m
WHERE {spec.condition}
{group}
"""


def calendar_sql(where: str, params: list[object], known: str) -> tuple[str, list[object]]:
    selects = "\nUNION ALL\n".join(calendar_select(spec, known) for spec in CALENDAR_DIMENSIONS)
    sql = f"""
WITH base AS (
    SELECT {KICKOFF_AT_SQL} AS kickoff_at, m.phase, m.spectators
    FROM ehf.match m
    {EDITION_JOINS}
    WHERE {where}
)
{selects}
"""
    return sql, list(params)


def calendar_cell_from_row(row: dict) -> CalendarCell:
    return CalendarCell(
        dimension=str(row["dimension"]),
        key=str(row["key_a"]),
        secondary=None if row["key_b"] is None else str(row["key_b"]),
        played=int(row["played"]),
        known=int(row["known"]),
        mean=row["mean"],
    )


def record_sql(
    spec: RecordSpec, where: str, params: list[object], known: str
) -> tuple[str, list[object]]:
    distinct = f"DISTINCT ON ({spec.partition}) " if spec.partition else ""
    partition_order = f"{spec.partition}, " if spec.partition else ""
    limit = "LIMIT %s" if spec.limit is not None else ""
    sql = f"""
SELECT * FROM (
    SELECT {distinct}{RECORD_COLUMNS}
    {RECORD_SOURCE}
    WHERE {where} AND {known} {spec.extra_where}
    ORDER BY {partition_order}m.spectators DESC, {KICKOFF_AT_SQL} DESC NULLS LAST, m.id DESC
) ranked
ORDER BY {spec.outer_order}
{limit}
"""
    extra = [*params, *spec.extra_params]
    return sql, extra if spec.limit is None else [*extra, spec.limit]


def record_from_row(row: dict) -> AttendanceRecord:
    return AttendanceRecord(
        match_id=int(row["id"]),
        kickoff=row["kickoff_at"],
        season=str(row["season_code"]),
        competition=str(row["competition_name"]),
        home=str(row["home_name"]),
        away=str(row["away_name"]),
        home_goals=row["score_home"],
        away_goals=row["score_away"],
        venue=row["venue_name"],
        spectators=int(row["spectators"]),
    )
