from __future__ import annotations

from collections.abc import Callable

from psycopg import Connection, Error
from psycopg.rows import dict_row

from ehf.domain.errors import DataReadError
from ehf.domain.matches import Choice
from ehf.domain.scorers import ScorerFilterOptions, ScorerFilters, ScorerListItem, ScorerListPage
from ehf.infrastructure.ordering import order_sql
from ehf.infrastructure.played import EDITION_JOINS, PLAYED_SQL

TEAM_NAME = "COALESCE(ed.display_name, t.display_name)"

SCORER_BASE = f"""
FROM ehf.match_lineup l
JOIN ehf.match_team t ON t.id = l.match_team_id
JOIN ehf.match m ON m.id = t.match_id
{EDITION_JOINS}
LEFT JOIN ehf.club_edition ed
    ON ed.club_id = t.club_id
   AND ed.competition_edition_id = m.competition_edition_id
JOIN ehf.match_player_stat ps ON ps.lineup_id = l.id
JOIN ehf.person p ON p.id = l.person_id
WHERE l.person_id IS NOT NULL AND {PLAYED_SQL}
"""

SCORER_GROUP = f"""
SELECT
    p.id AS player_id,
    p.display_name,
    SUM(COALESCE(ps.goals, 0))::int AS goals,
    COUNT(DISTINCT m.id)::int AS matches,
    string_agg(DISTINCT {TEAM_NAME}, ', ' ORDER BY {TEAM_NAME}) AS teams
{SCORER_BASE}
{{where}}
GROUP BY p.id, p.display_name
HAVING SUM(COALESCE(ps.goals, 0)) > 0
"""

SCORER_ORDER = {
    "player": ("display_name",),
    "team": ("teams",),
    "goals": ("goals",),
    "matches": ("matches",),
}


class PsycopgScorerListReader:
    def __init__(self, connect: Callable[[], Connection]) -> None:
        self._connect = connect

    def fetch_page(self, filters: ScorerFilters) -> ScorerListPage:
        where, params = self._where(filters)
        grouped = SCORER_GROUP.format(where=where)
        ranked = (
            f"SELECT player_id, display_name, goals, matches, teams, "
            f"ROW_NUMBER() OVER (ORDER BY goals DESC, matches DESC, display_name) AS rank "
            f"FROM ({grouped}) scorers"
        )
        count_sql = f"SELECT COUNT(*) FROM ({grouped}) listed"
        page_sql = (
            f"{ranked} {order_sql(filters.sort, SCORER_ORDER, 'rank')} "
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
            raise DataReadError(f"Could not read scorers: {exc}") from exc
        return ScorerListPage(tuple(self._item(row) for row in rows), total, filters)

    def fetch_options(self) -> ScorerFilterOptions:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "SELECT id::text AS value, code AS label FROM ehf.season ORDER BY year_start DESC"
                    )
                    seasons = tuple(Choice(row["value"], row["label"]) for row in cursor.fetchall())
                    cursor.execute(
                        "SELECT id::text AS value, name AS label FROM ehf.competition ORDER BY name"
                    )
                    competitions = tuple(
                        Choice(row["value"], row["label"]) for row in cursor.fetchall()
                    )
        except Error as exc:
            raise DataReadError(f"Could not read scorer filters: {exc}") from exc
        return ScorerFilterOptions(seasons, competitions)

    def _where(self, filters: ScorerFilters) -> tuple[str, list[object]]:
        clauses: list[str] = []
        params: list[object] = []
        if filters.season_id is not None:
            clauses.append("s.id = %s")
            params.append(filters.season_id)
        if filters.competition_id is not None:
            clauses.append("c.id = %s")
            params.append(filters.competition_id)
        if not clauses:
            return "", params
        return "AND " + " AND ".join(clauses), params

    def _item(self, row: dict) -> ScorerListItem:
        return ScorerListItem(
            rank=int(row["rank"]),
            player_id=row["player_id"],
            display_name=row["display_name"],
            teams=row["teams"],
            goals=int(row["goals"] or 0),
            matches=int(row["matches"] or 0),
        )
