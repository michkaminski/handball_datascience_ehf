from __future__ import annotations

from collections.abc import Callable

from psycopg import Connection, Error
from psycopg.rows import dict_row

from ehf.domain.errors import DataReadError
from ehf.domain.matches import Choice
from ehf.domain.teams import TeamFilters, TeamListItem, TeamListPage
from ehf.infrastructure.ordering import order_sql

TEAM_FROM = """
FROM ehf.club_edition ed
JOIN ehf.club cl ON cl.id = ed.club_id
JOIN ehf.competition_edition ce ON ce.id = ed.competition_edition_id
JOIN ehf.season s ON s.id = ce.season_id
JOIN ehf.competition c ON c.id = ce.competition_id
LEFT JOIN ehf.match m
    ON m.competition_edition_id = ce.id
   AND cl.id IN (m.home_club_id, m.away_club_id)
LEFT JOIN LATERAL (
    SELECT v.city
    FROM ehf.match hm
    JOIN ehf.competition_edition hce ON hce.id = hm.competition_edition_id
    JOIN ehf.venue v ON v.id = hm.venue_id
    WHERE hm.home_club_id = cl.id
      AND hce.season_id = s.id
      AND v.city IS NOT NULL
    GROUP BY v.city
    ORDER BY COUNT(*) DESC, v.city
    LIMIT 1
) home_city ON TRUE
"""

TEAM_SELECT = """
SELECT
    cl.id,
    s.id AS season_id,
    s.code AS season_code,
    MODE() WITHIN GROUP (ORDER BY ed.display_name) AS name,
    string_agg(DISTINCT c.gender, ',' ORDER BY c.gender) AS genders,
    COUNT(DISTINCT m.id)::int AS matches,
    CASE WHEN COUNT(DISTINCT m.id) > 0 THEN 'active' ELSE 'listed' END AS status,
    home_city.city
"""

TEAM_GROUP = "GROUP BY cl.id, s.id, s.code, s.year_start, home_city.city"

TEAM_ORDER = {
    "id": ("cl.id",),
    "season": ("s.year_start",),
    "name": ("name",),
    "gender": ("genders",),
    "city": ("home_city.city",),
    "matches": ("matches",),
    "status": ("status",),
}

SEASONS_SQL = (
    "SELECT id::text AS value, code AS label FROM ehf.season ORDER BY year_start DESC"
)


class PsycopgTeamListReader:
    def __init__(self, connect: Callable[[], Connection]) -> None:
        self._connect = connect

    def fetch_page(self, filters: TeamFilters) -> TeamListPage:
        where, params = self._where(filters)
        select_sql = f"{TEAM_SELECT} {TEAM_FROM} {where}"
        count_sql = f"SELECT COUNT(*) FROM ({select_sql}) listed"
        page_sql = (
            f"{select_sql} {order_sql(filters.sort, TEAM_ORDER, 'name ASC, cl.id')} "
            "LIMIT %s OFFSET %s"
        )
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(count_sql, params)
                    total = int(cursor.fetchone()[0])
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        page_sql,
                        (*params, filters.page_size, (filters.page - 1) * filters.page_size),
                    )
                    rows = cursor.fetchall()
        except Error as exc:
            raise DataReadError(f"Could not read teams: {exc}") from exc
        return TeamListPage(tuple(self._item(row) for row in rows), total, filters)

    def fetch_seasons(self) -> tuple[Choice, ...]:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(SEASONS_SQL)
                    return tuple(Choice(row["value"], row["label"]) for row in cursor.fetchall())
        except Error as exc:
            raise DataReadError(f"Could not read team filters: {exc}") from exc

    def _where(self, filters: TeamFilters) -> tuple[str, list[object]]:
        clauses: list[str] = []
        params: list[object] = []
        if filters.season_id is not None:
            clauses.append("s.id = %s")
            params.append(filters.season_id)
        if filters.gender:
            clauses.append("c.gender = %s")
            params.append(filters.gender)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        having = ""
        if filters.query:
            having = "HAVING bool_or(ed.display_name ILIKE %s)"
            params.append(f"%{filters.query}%")
        return f"{where} {TEAM_GROUP} {having}", params

    def _item(self, row: dict) -> TeamListItem:
        return TeamListItem(
            id=row["id"],
            season_id=row["season_id"],
            season_code=row["season_code"],
            name=row["name"],
            genders=row["genders"] or "",
            city=row["city"],
            matches=int(row["matches"] or 0),
            status=row["status"],
        )
