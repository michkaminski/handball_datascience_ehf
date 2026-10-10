from __future__ import annotations

from ehf.domain.attendance_cities import (
    UNKNOWN_CLUB_NAME,
    CityAttendance,
    CityContribution,
)
from ehf.infrastructure.played import EDITION_JOINS, HOME_NAME, TEAM_JOINS

VENUE_JOIN = "LEFT JOIN ehf.venue v ON v.id = m.venue_id"
CITY_SPELLING_SQL = r"regexp_replace(btrim(v.city), '\s+', ' ', 'g')"
CITY_KEY_SQL = f"NULLIF(lower({CITY_SPELLING_SQL}), '')"
CITY_LABEL_SQL = f"MODE() WITHIN GROUP (ORDER BY {CITY_SPELLING_SQL})"
COMPETITION_SQL = "COALESCE(NULLIF(btrim(c.name), ''), '—')"
CLUB_NAME_SQL = f"NULLIF(btrim({HOME_NAME}), '')"


def known_columns(known: str) -> str:
    return f"""
    COUNT(*)::int AS played,
    (COUNT(*) FILTER (WHERE {known}))::int AS known,
    COALESCE((SUM(m.spectators) FILTER (WHERE {known})), 0)::bigint AS total,
    (AVG(m.spectators) FILTER (WHERE {known}))::float8 AS mean,
    (percentile_cont(0.5) WITHIN GROUP (ORDER BY m.spectators) FILTER (WHERE {known}))::float8 AS median,
    (MODE() WITHIN GROUP (ORDER BY m.spectators) FILTER (WHERE {known}))::int AS spectator_mode,
    (MAX(m.spectators) FILTER (WHERE {known}))::int AS maximum
"""


def ranked_city_keys_cte(where: str, known: str) -> str:
    return f"""
ranked AS (
    SELECT {CITY_KEY_SQL} AS city_key
    FROM ehf.match m
    {EDITION_JOINS}
    {VENUE_JOIN}
    WHERE {where} AND {CITY_KEY_SQL} IS NOT NULL
    GROUP BY {CITY_KEY_SQL}
    HAVING COUNT(*) FILTER (WHERE {known}) > 0
    ORDER BY
        COALESCE((SUM(m.spectators) FILTER (WHERE {known})), 0) DESC,
        COUNT(*) FILTER (WHERE {known}) DESC,
        city_key
    LIMIT %s
)
"""


def cities_sql(
    where: str, params: list[object], known: str, limit: int
) -> tuple[str, list[object]]:
    sql = f"""
SELECT
    {CITY_KEY_SQL} AS city_key,
    {CITY_LABEL_SQL} AS city,
    {known_columns(known)},
    COUNT(DISTINCT m.home_club_id)::int AS club_count,
    COUNT(DISTINCT {COMPETITION_SQL})::int AS competition_count
FROM ehf.match m
{EDITION_JOINS}
{VENUE_JOIN}
WHERE {where} AND {CITY_KEY_SQL} IS NOT NULL
GROUP BY {CITY_KEY_SQL}
HAVING COUNT(*) FILTER (WHERE {known}) > 0
ORDER BY total DESC, known DESC, city_key
LIMIT %s
"""
    return sql, [*params, limit]


def city_contributions_sql(
    where: str, params: list[object], known: str, limit: int
) -> tuple[str, list[object]]:
    sql = f"""
SELECT
    {CITY_KEY_SQL} AS city_key,
    {CITY_LABEL_SQL} AS city,
    m.home_club_id AS club_id,
    COALESCE(
        (ARRAY_AGG({CLUB_NAME_SQL} ORDER BY s.year_start DESC)
            FILTER (WHERE {CLUB_NAME_SQL} IS NOT NULL))[1],
        '{UNKNOWN_CLUB_NAME}'
    ) AS club_name,
    {COMPETITION_SQL} AS competition,
    {known_columns(known)}
FROM ehf.match m
{EDITION_JOINS}
{TEAM_JOINS}
{VENUE_JOIN}
WHERE {where} AND {CITY_KEY_SQL} IS NOT NULL
GROUP BY {CITY_KEY_SQL}, m.home_club_id, {COMPETITION_SQL}
HAVING COUNT(*) FILTER (WHERE {known}) > 0
ORDER BY total DESC, city_key, club_name, competition
LIMIT %s
"""
    return sql, [*params, limit]


def matches_without_city_sql(where: str, params: list[object]) -> tuple[str, list[object]]:
    sql = f"""
SELECT COUNT(*)::int AS missing
FROM ehf.match m
{EDITION_JOINS}
{VENUE_JOIN}
WHERE {where} AND {CITY_KEY_SQL} IS NULL
"""
    return sql, list(params)


def city_from_row(row: dict) -> CityAttendance:
    return CityAttendance(
        city=str(row["city"]),
        played=int(row["played"]),
        known=int(row["known"]),
        total=int(row["total"]),
        mean=row["mean"],
        median=row["median"],
        mode=row["spectator_mode"],
        maximum=row["maximum"],
        club_count=int(row["club_count"]),
        competition_count=int(row["competition_count"]),
    )


def contribution_from_row(row: dict) -> CityContribution:
    club_id = row["club_id"]
    return CityContribution(
        city=str(row["city"]),
        club_id=None if club_id is None else int(club_id),
        club_name=str(row["club_name"]),
        competition=str(row["competition"]),
        played=int(row["played"]),
        known=int(row["known"]),
        total=int(row["total"]),
        mean=row["mean"],
        maximum=row["maximum"],
        median=row["median"],
        mode=row["spectator_mode"],
    )
