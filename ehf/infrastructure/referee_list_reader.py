from __future__ import annotations

from collections.abc import Callable

from psycopg import Connection, Error
from psycopg.rows import dict_row

from ehf.domain.errors import DataReadError
from ehf.domain.matches import Choice
from ehf.domain.referees import RefereeFilterOptions, RefereeFilters, RefereeListItem, RefereeListPage
from ehf.infrastructure.ordering import order_sql

GROUPED = """
SELECT MIN(o.id) AS id,
    MAX(o.display_name) AS display_name,
    MAX(o.first_name) AS first_name,
    MAX(o.last_name) AS last_name,
    MAX(o.source_name) AS source_name,
    MAX(o.country_code) AS country_code,
    COUNT(DISTINCT o.match_id) AS matches
FROM ehf.match_official o
WHERE o.role = 'referee'
GROUP BY o.display_name, o.first_name, o.last_name, o.country_code
"""

REFEREE_ORDER = {
    "id": ("r.id",),
    "name": ("r.last_name", "r.first_name", "r.display_name"),
    "country": ("COALESCE(ct.name, r.country_code)",),
    "matches": ("r.matches",),
}


class PsycopgRefereeListReader:
    def __init__(self, connect: Callable[[], Connection]) -> None:
        self._connect = connect

    def fetch_page(self, filters: RefereeFilters) -> RefereeListPage:
        where, params = self._where(filters)
        from_sql = f"FROM ({GROUPED}) r LEFT JOIN ehf.country ct ON ct.code = r.country_code {where}"
        count_sql = f"SELECT COUNT(*) {from_sql}"
        page_sql = (
            "SELECT r.id, r.display_name, r.first_name, r.last_name, r.country_code, "
            f"ct.name AS country_name, r.matches {from_sql} "
            f"{order_sql(filters.sort, REFEREE_ORDER, 'r.id')} LIMIT %s OFFSET %s"
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
            raise DataReadError(f"Could not read referees: {exc}") from exc
        return RefereeListPage(tuple(self._item(row) for row in rows), total, filters)

    def fetch_options(self) -> RefereeFilterOptions:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "SELECT DISTINCT o.country_code AS value, COALESCE(ct.name, o.country_code) AS label "
                        "FROM ehf.match_official o "
                        "LEFT JOIN ehf.country ct ON ct.code = o.country_code "
                        "WHERE o.role = 'referee' AND o.country_code IS NOT NULL "
                        "ORDER BY 2"
                    )
                    countries = tuple(Choice(row["value"], row["label"]) for row in cursor.fetchall())
        except Error as exc:
            raise DataReadError(f"Could not read referee filters: {exc}") from exc
        return RefereeFilterOptions(countries)

    def _where(self, filters: RefereeFilters) -> tuple[str, list[object]]:
        clauses: list[str] = []
        params: list[object] = []
        if filters.query:
            clauses.append(
                "(r.display_name ILIKE %s OR r.first_name ILIKE %s OR r.last_name ILIKE %s OR r.source_name ILIKE %s)"
            )
            pattern = f"%{filters.query}%"
            params.extend((pattern, pattern, pattern, pattern))
        if filters.country:
            clauses.append("r.country_code = %s")
            params.append(filters.country)
        if not clauses:
            return "", params
        return "WHERE " + " AND ".join(clauses), params

    def _item(self, row: dict) -> RefereeListItem:
        return RefereeListItem(
            id=row["id"],
            display_name=row["display_name"] or row["last_name"] or row["first_name"] or "—",
            first_name=row["first_name"],
            last_name=row["last_name"],
            country_code=row["country_code"],
            country_name=row["country_name"],
            matches=int(row["matches"] or 0),
        )
