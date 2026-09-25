from __future__ import annotations

from collections.abc import Callable

from psycopg import Connection, Error
from psycopg.rows import dict_row

from ehf.domain.errors import DataReadError
from ehf.domain.seasons import SeasonFilters, SeasonListItem, SeasonListPage
from ehf.infrastructure.ordering import order_sql

SEASON_FROM = """
FROM ehf.season s
LEFT JOIN (
    SELECT season_id, COUNT(*)::int AS competitions
    FROM ehf.competition_edition
    GROUP BY season_id
) edition_counts ON edition_counts.season_id = s.id
LEFT JOIN (
    SELECT ce.season_id,
           COUNT(m.id)::int AS matches,
           COUNT(m.id) FILTER (WHERE m.status = 'scheduled_or_no_result')::int AS scheduled
    FROM ehf.competition_edition ce
    LEFT JOIN ehf.match m ON m.competition_edition_id = ce.id
    GROUP BY ce.season_id
) match_counts ON match_counts.season_id = s.id
"""

STATE_SQL = """
CASE
    WHEN COALESCE(edition_counts.competitions, 0) = 0
      OR COALESCE(match_counts.matches, 0) = 0 THEN 'empty'
    WHEN COALESCE(match_counts.scheduled, 0) > 0 THEN 'open'
    ELSE 'complete'
END
"""

SEASON_ORDER = {
    "id": ("s.id",),
    "season": ("s.code",),
    "year": ("s.year_start",),
    "competitions": ("COALESCE(edition_counts.competitions, 0)",),
    "matches": ("COALESCE(match_counts.matches, 0)",),
    "state": (STATE_SQL,),
}


class PsycopgSeasonListReader:
    def __init__(self, connect: Callable[[], Connection]) -> None:
        self._connect = connect

    def fetch_page(self, filters: SeasonFilters) -> SeasonListPage:
        where, params = self._where(filters)
        select_sql = (
            "SELECT s.id, s.code, s.year_start, "
            "COALESCE(edition_counts.competitions, 0) AS competitions, "
            "COALESCE(match_counts.matches, 0) AS matches, "
            f"{STATE_SQL} AS state {SEASON_FROM} {where}"
        )
        count_sql = f"SELECT COUNT(*) FROM ({select_sql}) listed"
        page_sql = (
            f"{select_sql} {order_sql(filters.sort, SEASON_ORDER, 's.id')} "
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
            raise DataReadError(f"Could not read seasons: {exc}") from exc
        return SeasonListPage(tuple(self._item(row) for row in rows), total, filters)

    def _where(self, filters: SeasonFilters) -> tuple[str, list[object]]:
        clauses: list[str] = []
        params: list[object] = []
        if filters.query:
            clauses.append(
                "(s.code ILIKE %s OR s.year_start::text ILIKE %s OR s.year_end::text ILIKE %s)"
            )
            pattern = f"%{filters.query}%"
            params.extend((pattern, pattern, pattern))
        if filters.state:
            clauses.append(f"({STATE_SQL}) = %s")
            params.append(filters.state)
        if not clauses:
            return "", params
        return "WHERE " + " AND ".join(clauses), params

    def _item(self, row: dict) -> SeasonListItem:
        return SeasonListItem(
            id=row["id"],
            code=row["code"],
            year_start=int(row["year_start"]),
            competitions=int(row["competitions"] or 0),
            matches=int(row["matches"] or 0),
            state=row["state"],
        )
