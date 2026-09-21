from __future__ import annotations

from collections.abc import Callable

from psycopg import Connection, Error
from psycopg.rows import dict_row

from ehf.domain.errors import DataReadError
from ehf.domain.matches import Choice
from ehf.domain.venues import VenueFilterOptions, VenueFilters, VenueListItem, VenueListPage
from ehf.infrastructure.ordering import order_sql
from ehf.infrastructure.played import PLAYED_SQL

VENUE_ORDER = {
    "id": ("v.id",),
    "name": ("v.name",),
    "city": ("v.city",),
    "country": ("COALESCE(ct.name, v.country_code)",),
    "matches": ("played_matches",),
}


class PsycopgVenueListReader:
    def __init__(self, connect: Callable[[], Connection]) -> None:
        self._connect = connect

    def fetch_page(self, filters: VenueFilters) -> VenueListPage:
        where, params = self._where(filters)
        from_sql = (
            "FROM ehf.venue v "
            "LEFT JOIN ehf.country ct ON ct.code = v.country_code "
            f"LEFT JOIN ehf.match m ON m.venue_id = v.id AND {PLAYED_SQL} "
            f"{where} GROUP BY v.id, ct.name"
        )
        count_sql = f"SELECT COUNT(*) FROM (SELECT v.id {from_sql}) listed"
        page_sql = (
            "SELECT v.id, v.name, v.city, v.country_code, ct.name AS country_name, "
            f"COUNT(m.id) AS played_matches {from_sql} "
            f"{order_sql(filters.sort, VENUE_ORDER, 'v.id')} LIMIT %s OFFSET %s"
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
            raise DataReadError(f"Could not read venues: {exc}") from exc
        return VenueListPage(tuple(self._item(row) for row in rows), total, filters)

    def fetch_options(self) -> VenueFilterOptions:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "SELECT DISTINCT city AS value, city AS label FROM ehf.venue "
                        "WHERE city IS NOT NULL ORDER BY city"
                    )
                    cities = tuple(Choice(row["value"], row["label"]) for row in cursor.fetchall())
        except Error as exc:
            raise DataReadError(f"Could not read venue filters: {exc}") from exc
        return VenueFilterOptions(cities)

    def _where(self, filters: VenueFilters) -> tuple[str, list[object]]:
        clauses: list[str] = []
        params: list[object] = []
        if filters.query:
            clauses.append("(v.name ILIKE %s OR v.city ILIKE %s)")
            pattern = f"%{filters.query}%"
            params.extend((pattern, pattern))
        if filters.city:
            clauses.append("v.city = %s")
            params.append(filters.city)
        if not clauses:
            return "", params
        return "WHERE " + " AND ".join(clauses), params

    def _item(self, row: dict) -> VenueListItem:
        return VenueListItem(
            id=row["id"],
            name=row["name"],
            city=row["city"],
            country_code=row["country_code"],
            country_name=row["country_name"],
            matches=int(row["played_matches"] or 0),
        )
