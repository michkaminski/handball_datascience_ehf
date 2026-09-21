from __future__ import annotations

from collections.abc import Callable

from psycopg import Connection, Error
from psycopg.rows import dict_row

from ehf.domain.errors import DataReadError
from ehf.domain.matches import (
    Choice,
    MatchFilterOptions,
    MatchFilters,
    MatchListItem,
    MatchListPage,
)
from ehf.infrastructure.kickoff import KICKOFF_AT_SQL
from ehf.infrastructure.ordering import order_sql

LIST_SQL = f"""
SELECT
    m.id,
    {KICKOFF_AT_SQL} AS kickoff_at,
    s.code AS season_code,
    c.name AS competition_name,
    COALESCE(home_ed.display_name, home_team.display_name) AS home_name,
    COALESCE(away_ed.display_name, away_team.display_name) AS away_name,
    COALESCE(m.score_home, home_team.goals) AS score_home,
    COALESCE(m.score_away, away_team.goals) AS score_away,
    m.result_type,
    m.status,
    v.name AS venue_name,
    m.phase,
    m.group_code
FROM ehf.match m
JOIN ehf.competition_edition ce ON ce.id = m.competition_edition_id
JOIN ehf.season s ON s.id = ce.season_id
JOIN ehf.competition c ON c.id = ce.competition_id
LEFT JOIN ehf.club_edition home_ed
    ON home_ed.club_id = m.home_club_id
   AND home_ed.competition_edition_id = m.competition_edition_id
LEFT JOIN ehf.club_edition away_ed
    ON away_ed.club_id = m.away_club_id
   AND away_ed.competition_edition_id = m.competition_edition_id
LEFT JOIN ehf.match_team home_team
    ON home_team.match_id = m.id AND home_team.side = 'home'
LEFT JOIN ehf.match_team away_team
    ON away_team.match_id = m.id AND away_team.side = 'away'
LEFT JOIN ehf.venue v ON v.id = m.venue_id
"""

MATCH_ORDER = {
    "id": ("m.id",),
    "date": (KICKOFF_AT_SQL,),
    "time": (f"({KICKOFF_AT_SQL}::time)",),
    "season": ("s.code",),
    "competition": ("c.name",),
    "phase": ("m.phase", "m.group_code"),
    "home": ("COALESCE(home_ed.display_name, home_team.display_name)",),
    "score": (
        "COALESCE(m.score_home, home_team.goals)",
        "COALESCE(m.score_away, away_team.goals)",
    ),
    "away": ("COALESCE(away_ed.display_name, away_team.display_name)",),
    "venue": ("v.name",),
}


class PsycopgMatchListReader:
    def __init__(self, connect: Callable[[], Connection]) -> None:
        self._connect = connect

    def fetch_page(self, filters: MatchFilters) -> MatchListPage:
        where, params = self._where(filters)
        count_sql = f"SELECT COUNT(*) FROM ({LIST_SQL} {where}) AS listed"
        page_sql = (
            f"{LIST_SQL} {where} {order_sql(filters.sort, MATCH_ORDER, 'm.id')} "
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
                        (
                            *params,
                            filters.page_size,
                            (filters.page - 1) * filters.page_size,
                        ),
                    )
                    rows = cursor.fetchall()
        except Error as exc:
            raise DataReadError(f"Could not read ehf.match: {exc}") from exc
        items = tuple(self._item(row) for row in rows)
        return MatchListPage(items=items, total=total, filters=filters)

    def fetch_options(self) -> MatchFilterOptions:
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
                    phases = self._choices(
                        cursor,
                        "SELECT DISTINCT phase AS value, phase AS label "
                        "FROM ehf.match WHERE phase IS NOT NULL ORDER BY phase",
                    )
                    groups = self._choices(
                        cursor,
                        "SELECT DISTINCT group_code AS value, group_code AS label "
                        "FROM ehf.match WHERE group_code IS NOT NULL ORDER BY group_code",
                    )
                    venues = self._choices(
                        cursor,
                        "SELECT id::text AS value, name AS label FROM ehf.venue ORDER BY name",
                    )
        except Error as exc:
            raise DataReadError(f"Could not read match filter options: {exc}") from exc
        return MatchFilterOptions(
            seasons=seasons,
            competitions=competitions,
            phases=phases,
            groups=groups,
            venues=venues,
        )

    def _where(self, filters: MatchFilters) -> tuple[str, list[object]]:
        clauses: list[str] = []
        params: list[object] = []
        if filters.season_id is not None:
            clauses.append("s.id = %s")
            params.append(filters.season_id)
        if filters.competition_id is not None:
            clauses.append("c.id = %s")
            params.append(filters.competition_id)
        if filters.phase:
            clauses.append("m.phase = %s")
            params.append(filters.phase)
        if filters.group_code:
            clauses.append("m.group_code = %s")
            params.append(filters.group_code)
        if filters.venue_id is not None:
            clauses.append("v.id = %s")
            params.append(filters.venue_id)
        if filters.club_query:
            clauses.append(
                "(COALESCE(home_ed.display_name, home_team.display_name) ILIKE %s "
                "OR COALESCE(away_ed.display_name, away_team.display_name) ILIKE %s)"
            )
            pattern = f"%{filters.club_query}%"
            params.extend((pattern, pattern))
        if filters.match_date is not None:
            clauses.append(f"{KICKOFF_AT_SQL}::date = %s")
            params.append(filters.match_date)
        if not clauses:
            return "", params
        return "WHERE " + " AND ".join(clauses), params

    def _choices(self, cursor, sql: str) -> tuple[Choice, ...]:
        cursor.execute(sql)
        return tuple(Choice(value=row["value"], label=row["label"]) for row in cursor.fetchall())

    def _item(self, row: dict) -> MatchListItem:
        return MatchListItem(
            id=row["id"],
            kickoff_at=row["kickoff_at"],
            season_code=row["season_code"],
            competition_name=row["competition_name"],
            home_name=row["home_name"],
            away_name=row["away_name"],
            score_home=row["score_home"],
            score_away=row["score_away"],
            result_type=row["result_type"],
            status=row["status"],
            venue_name=row["venue_name"],
            phase=row["phase"],
            group_code=row["group_code"],
        )
