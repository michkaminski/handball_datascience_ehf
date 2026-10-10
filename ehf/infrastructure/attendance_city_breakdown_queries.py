from __future__ import annotations

from ehf.domain.attendance_city_breakdown import CityCompetition, CitySeason, CityVenue
from ehf.infrastructure.attendance_cities_queries import (
    CITY_KEY_SQL,
    CITY_LABEL_SQL,
    COMPETITION_SQL,
    VENUE_JOIN,
    known_columns,
    ranked_city_keys_cte,
)
from ehf.infrastructure.played import EDITION_JOINS

VENUE_NAME_SQL = "COALESCE(NULLIF(btrim(v.name), ''), '—')"


def _ranked_cities_query(
    select: str,
    group_by: str,
    order_by: str,
    where: str,
    params: list[object],
    known: str,
    city_limit: int,
) -> tuple[str, list[object]]:
    sql = f"""
WITH {ranked_city_keys_cte(where, known)}
SELECT
    {CITY_KEY_SQL} AS city_key,
    {CITY_LABEL_SQL} AS city,
    {select},
    {known_columns(known)}
FROM ehf.match m
{EDITION_JOINS}
{VENUE_JOIN}
WHERE {where} AND {CITY_KEY_SQL} IN (SELECT city_key FROM ranked)
GROUP BY {CITY_KEY_SQL}, {group_by}
HAVING COUNT(*) FILTER (WHERE {known}) > 0
ORDER BY {order_by}
"""
    return sql, [*params, city_limit, *params]


def city_seasons_sql(
    where: str, params: list[object], known: str, city_limit: int
) -> tuple[str, list[object]]:
    return _ranked_cities_query(
        "s.code AS season_code, s.year_start",
        "s.id, s.code, s.year_start",
        "city_key, s.year_start",
        where,
        params,
        known,
        city_limit,
    )


def city_competitions_sql(
    where: str, params: list[object], known: str, city_limit: int
) -> tuple[str, list[object]]:
    return _ranked_cities_query(
        f"{COMPETITION_SQL} AS competition",
        COMPETITION_SQL,
        "city_key, total DESC, competition",
        where,
        params,
        known,
        city_limit,
    )


def city_venues_sql(
    where: str, params: list[object], known: str, city_limit: int
) -> tuple[str, list[object]]:
    return _ranked_cities_query(
        f"v.id AS venue_id, {VENUE_NAME_SQL} AS venue_name",
        "v.id, v.name",
        "city_key, total DESC, venue_name, venue_id",
        where,
        params,
        known,
        city_limit,
    )


def season_from_row(row: dict) -> CitySeason:
    return CitySeason(
        city=str(row["city"]),
        season_code=str(row["season_code"]),
        year_start=int(row["year_start"]),
        played=int(row["played"]),
        known=int(row["known"]),
        total=int(row["total"]),
        mean=row["mean"],
        median=row["median"],
        maximum=row["maximum"],
        mode=row["spectator_mode"],
    )


def competition_from_row(row: dict) -> CityCompetition:
    return CityCompetition(
        city=str(row["city"]),
        competition=str(row["competition"]),
        played=int(row["played"]),
        known=int(row["known"]),
        total=int(row["total"]),
        mean=row["mean"],
        median=row["median"],
        maximum=row["maximum"],
        mode=row["spectator_mode"],
    )


def venue_from_row(row: dict) -> CityVenue:
    return CityVenue(
        city=str(row["city"]),
        venue_id=int(row["venue_id"]),
        venue_name=str(row["venue_name"]),
        played=int(row["played"]),
        known=int(row["known"]),
        total=int(row["total"]),
        mean=row["mean"],
        maximum=row["maximum"],
        median=row["median"],
        mode=row["spectator_mode"],
    )
