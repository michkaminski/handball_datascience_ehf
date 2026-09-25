from __future__ import annotations

from collections.abc import Callable

from psycopg import Connection, Error
from psycopg.rows import dict_row

from ehf.domain.competitions import (
    CompetitionFilterOptions,
    CompetitionFilters,
    CompetitionListItem,
    CompetitionListPage,
)
from ehf.domain.errors import DataReadError
from ehf.domain.matches import Choice
from ehf.infrastructure.ordering import order_sql

COMPETITION_FROM = """
FROM ehf.competition_edition ce
JOIN ehf.season s ON s.id = ce.season_id
JOIN ehf.competition c ON c.id = ce.competition_id
LEFT JOIN (
    SELECT competition_edition_id, COUNT(DISTINCT club_id)::int AS teams
    FROM ehf.club_edition
    GROUP BY competition_edition_id
) team_counts ON team_counts.competition_edition_id = ce.id
LEFT JOIN (
    SELECT competition_edition_id, COUNT(*)::int AS matches
    FROM ehf.match
    GROUP BY competition_edition_id
) match_counts ON match_counts.competition_edition_id = ce.id
"""

COMPETITION_ORDER = {
    "id": ("ce.id",),
    "season": ("s.year_start", "s.code"),
    "name": ("c.name",),
    "gender": ("c.gender",),
    "teams": ("COALESCE(team_counts.teams, 0)",),
    "matches": ("COALESCE(match_counts.matches, 0)",),
}

SEASONS_SQL = (
    "SELECT id::text AS value, code AS label FROM ehf.season ORDER BY year_start DESC"
)


class PsycopgCompetitionListReader:
    def __init__(self, connect: Callable[[], Connection]) -> None:
        self._connect = connect

    def fetch_page(self, filters: CompetitionFilters) -> CompetitionListPage:
        where, params = self._where(filters)
        select_sql = (
            "SELECT ce.id, ce.competition_id, ce.season_id, s.code AS season_code, "
            "c.name, c.gender, "
            "COALESCE(team_counts.teams, 0) AS teams, "
            f"COALESCE(match_counts.matches, 0) AS matches {COMPETITION_FROM} {where}"
        )
        count_sql = f"SELECT COUNT(*) FROM ({select_sql}) listed"
        page_sql = (
            f"{select_sql} {order_sql(filters.sort, COMPETITION_ORDER, 'c.name ASC, ce.id')} "
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
            raise DataReadError(f"Could not read competitions: {exc}") from exc
        return CompetitionListPage(tuple(self._item(row) for row in rows), total, filters)

    def fetch_options(self) -> CompetitionFilterOptions:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(SEASONS_SQL)
                    seasons = tuple(
                        Choice(row["value"], row["label"]) for row in cursor.fetchall()
                    )
        except Error as exc:
            raise DataReadError(f"Could not read competition filters: {exc}") from exc
        return CompetitionFilterOptions(seasons)

    def _where(self, filters: CompetitionFilters) -> tuple[str, list[object]]:
        clauses: list[str] = []
        params: list[object] = []
        if filters.query:
            clauses.append("(c.name ILIKE %s OR c.code ILIKE %s)")
            pattern = f"%{filters.query}%"
            params.extend((pattern, pattern))
        if filters.season_id is not None:
            clauses.append("s.id = %s")
            params.append(filters.season_id)
        if not clauses:
            return "", params
        return "WHERE " + " AND ".join(clauses), params

    def _item(self, row: dict) -> CompetitionListItem:
        return CompetitionListItem(
            id=row["id"],
            competition_id=row["competition_id"],
            season_id=row["season_id"],
            season_code=row["season_code"],
            name=row["name"],
            gender=row["gender"],
            teams=int(row["teams"] or 0),
            matches=int(row["matches"] or 0),
        )
