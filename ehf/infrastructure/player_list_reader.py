from __future__ import annotations

from collections.abc import Callable

from psycopg import Connection, Error
from psycopg.rows import dict_row

from ehf.domain.errors import DataReadError
from ehf.domain.matches import Choice
from ehf.domain.players import PlayerFilterOptions, PlayerFilters, PlayerListItem, PlayerListPage
from ehf.infrastructure.ordering import order_sql

APPEARANCE_FROM = """
FROM ehf.match_lineup l
JOIN ehf.match_team t ON t.id = l.match_team_id
JOIN ehf.match m ON m.id = l.match_id
JOIN ehf.competition_edition ce ON ce.id = m.competition_edition_id
JOIN ehf.season s ON s.id = ce.season_id
JOIN ehf.competition c ON c.id = ce.competition_id
LEFT JOIN ehf.club_edition ed
    ON ed.club_id = t.club_id
   AND ed.competition_edition_id = m.competition_edition_id
"""

TEAM_NAME = "COALESCE(ed.display_name, t.display_name)"

PLAYER_ORDER = {
    "id": ("p.id",),
    "first_name": ("p.first_name",),
    "last_name": ("p.last_name", "p.first_name", "p.display_name"),
    "position": ("p.profile_position",),
    "teams": ("teams",),
    "year": ("EXTRACT(YEAR FROM p.birth_date)",),
    "height": ("p.height_cm",),
    "weight": ("p.weight_kg",),
}


class PsycopgPlayerListReader:
    def __init__(self, connect: Callable[[], Connection]) -> None:
        self._connect = connect

    def fetch_page(self, filters: PlayerFilters) -> PlayerListPage:
        appearance_sql, appearance_params = self._appearance_where(filters)
        person_sql, person_params = self._person_where(filters)
        exists_sql = (
            f"EXISTS (SELECT 1 {APPEARANCE_FROM} WHERE l.person_id = p.id{appearance_sql})"
        )
        teams_sql = (
            f"(SELECT string_agg(DISTINCT {TEAM_NAME}, ', ' ORDER BY {TEAM_NAME}) "
            f"{APPEARANCE_FROM} WHERE l.person_id = p.id{appearance_sql})"
        )
        from_sql = f"FROM ehf.person p WHERE {exists_sql}{person_sql}"
        count_sql = f"SELECT COUNT(*) {from_sql}"
        page_sql = (
            f"SELECT p.id, p.first_name, p.last_name, p.display_name, p.profile_position AS position, "
            f"EXTRACT(YEAR FROM p.birth_date)::int AS birth_year, p.height_cm, p.weight_kg, "
            f"{teams_sql} AS teams {from_sql} "
            f"{order_sql(filters.sort, PLAYER_ORDER, 'p.id')} "
            "LIMIT %s OFFSET %s"
        )
        params = (*appearance_params, *person_params)
        page_params = (*appearance_params, *appearance_params, *person_params)
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(count_sql, params)
                    total = int(cursor.fetchone()[0])
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        page_sql,
                        (
                            *page_params,
                            filters.page_size,
                            (filters.page - 1) * filters.page_size,
                        ),
                    )
                    rows = cursor.fetchall()
        except Error as exc:
            raise DataReadError(f"Could not read players: {exc}") from exc
        return PlayerListPage(
            items=tuple(self._item(row) for row in rows),
            total=total,
            filters=filters,
        )

    def fetch_options(self) -> PlayerFilterOptions:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    seasons = self._choices(
                        cursor,
                        "SELECT id::text AS value, code AS label FROM ehf.season ORDER BY year_start DESC",
                    )
                    competitions = self._choices(
                        cursor,
                        "SELECT id::text AS value, name AS label FROM ehf.competition ORDER BY name",
                    )
                    clubs = self._choices(
                        cursor,
                        f"SELECT t.club_id::text AS value, MIN({TEAM_NAME}) AS label "
                        f"{APPEARANCE_FROM} WHERE t.club_id IS NOT NULL "
                        f"GROUP BY t.club_id ORDER BY MIN({TEAM_NAME})",
                    )
                    positions = self._choices(
                        cursor,
                        "SELECT DISTINCT profile_position AS value, profile_position AS label "
                        "FROM ehf.person WHERE profile_position IS NOT NULL ORDER BY profile_position",
                    )
                    birth_years = self._choices(
                        cursor,
                        "SELECT year::text AS value, year::text AS label FROM ("
                        "SELECT DISTINCT EXTRACT(YEAR FROM birth_date)::int AS year "
                        "FROM ehf.person WHERE birth_date IS NOT NULL"
                        ") years ORDER BY year DESC",
                    )
        except Error as exc:
            raise DataReadError(f"Could not read player filter options: {exc}") from exc
        return PlayerFilterOptions(
            seasons=seasons,
            competitions=competitions,
            clubs=clubs,
            positions=positions,
            birth_years=birth_years,
        )

    def _appearance_where(self, filters: PlayerFilters) -> tuple[str, list[object]]:
        clauses: list[str] = []
        params: list[object] = []
        if filters.season_id is not None:
            clauses.append("s.id = %s")
            params.append(filters.season_id)
        if filters.competition_id is not None:
            clauses.append("c.id = %s")
            params.append(filters.competition_id)
        if filters.club_id is not None:
            clauses.append("t.club_id = %s")
            params.append(filters.club_id)
        if not clauses:
            return "", params
        return " AND " + " AND ".join(clauses), params

    def _person_where(self, filters: PlayerFilters) -> tuple[str, list[object]]:
        clauses: list[str] = []
        params: list[object] = []
        if filters.position:
            clauses.append("p.profile_position = %s")
            params.append(filters.position)
        if filters.birth_year is not None:
            clauses.append("EXTRACT(YEAR FROM p.birth_date)::int = %s")
            params.append(filters.birth_year)
        if filters.query:
            clauses.append(
                "(p.display_name ILIKE %s OR p.first_name ILIKE %s OR p.last_name ILIKE %s)"
            )
            pattern = f"%{filters.query}%"
            params.extend((pattern, pattern, pattern))
        if not clauses:
            return "", params
        return " AND " + " AND ".join(clauses), params

    def _choices(self, cursor, sql: str) -> tuple[Choice, ...]:
        cursor.execute(sql)
        return tuple(Choice(value=row["value"], label=row["label"]) for row in cursor.fetchall())

    def _item(self, row: dict) -> PlayerListItem:
        return PlayerListItem(
            id=row["id"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            display_name=row["display_name"] or "—",
            position=row["position"],
            teams=row["teams"],
            birth_year=row["birth_year"],
            height_cm=row["height_cm"],
            weight_kg=float(row["weight_kg"]) if row["weight_kg"] is not None else None,
        )
