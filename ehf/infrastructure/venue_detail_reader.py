from __future__ import annotations

from collections.abc import Callable

from psycopg import Connection, Error
from psycopg.rows import dict_row

from ehf.domain.errors import DataReadError, VenueNotFound
from ehf.domain.matches import Choice
from ehf.domain.venues import (
    VenueMatchFact,
    VenueMatchFilterOptions,
    VenueMatchFilters,
    VenueMatchItem,
    VenueMatchPage,
    VenuePlayerFilters,
    VenuePlayerItem,
    VenuePlayerPage,
    VenueProfile,
)
from ehf.infrastructure.kickoff import KICKOFF_AT_SQL
from ehf.infrastructure.ordering import order_sql
from ehf.infrastructure.played import (
    AWAY_NAME,
    EDITION_JOINS,
    HOME_NAME,
    PLAYED_SQL,
    SCORE_AWAY,
    SCORE_HOME,
    TEAM_JOINS,
)

MATCH_ORDER = {
    "date": (KICKOFF_AT_SQL,),
    "season": ("s.code",),
    "competition": ("c.name",),
    "home": (HOME_NAME,),
    "score": (SCORE_HOME, SCORE_AWAY),
    "away": (AWAY_NAME,),
}

PLAYER_ORDER = {
    "name": ("p.display_name",),
    "matches": ("matches",),
    "first": ("first_at",),
    "last": ("last_at",),
    "goals": ("goals",),
    "avg": ("CASE WHEN COUNT(DISTINCT l.match_id) > 0 THEN SUM(ps.goals)::numeric / COUNT(DISTINCT l.match_id) END",),
    "teams": ("teams",),
}

MATCH_FROM = f"""
FROM ehf.match m
{EDITION_JOINS}
{TEAM_JOINS}
WHERE m.venue_id = %s AND {PLAYED_SQL}
"""

PLAYER_FROM = f"""
FROM ehf.match_lineup l
JOIN ehf.match m ON m.id = l.match_id
JOIN ehf.match_team t ON t.id = l.match_team_id
LEFT JOIN ehf.club_edition ed
    ON ed.club_id = t.club_id AND ed.competition_edition_id = m.competition_edition_id
LEFT JOIN ehf.match_player_stat ps ON ps.lineup_id = l.id
JOIN ehf.person p ON p.id = l.person_id
WHERE m.venue_id = %s AND {PLAYED_SQL} AND l.person_id IS NOT NULL
"""


class PsycopgVenueDetailReader:
    def __init__(self, connect: Callable[[], Connection]) -> None:
        self._connect = connect

    def fetch_profile(self, venue_id: int) -> VenueProfile:
        played = PLAYED_SQL
        sql = f"""
        SELECT v.id, v.name, v.city, v.country_code, ct.name AS country_name,
            (SELECT MIN({KICKOFF_AT_SQL}) FROM ehf.match m WHERE m.venue_id = v.id AND {played}) AS first_match_at,
            (SELECT MAX({KICKOFF_AT_SQL}) FROM ehf.match m WHERE m.venue_id = v.id AND {played}) AS last_match_at,
            (SELECT COUNT(*) FROM ehf.match m WHERE m.venue_id = v.id) AS matches,
            (SELECT COUNT(*) FROM ehf.match m WHERE m.venue_id = v.id AND {played}) AS played_matches,
            (SELECT COUNT(DISTINCT ce.season_id) FROM ehf.match m
             JOIN ehf.competition_edition ce ON ce.id = m.competition_edition_id
             WHERE m.venue_id = v.id AND {played}) AS seasons,
            (SELECT COUNT(DISTINCT ce.competition_id) FROM ehf.match m
             JOIN ehf.competition_edition ce ON ce.id = m.competition_edition_id
             WHERE m.venue_id = v.id AND {played}) AS competitions,
            (SELECT COUNT(*) FROM (
                SELECT m.home_club_id AS club_id FROM ehf.match m
                WHERE m.venue_id = v.id AND {played} AND m.home_club_id IS NOT NULL
                UNION
                SELECT m.away_club_id FROM ehf.match m
                WHERE m.venue_id = v.id AND {played} AND m.away_club_id IS NOT NULL
            ) clubs) AS teams,
            (SELECT COUNT(DISTINCT l.person_id) FROM ehf.match_lineup l
             JOIN ehf.match m ON m.id = l.match_id
             WHERE m.venue_id = v.id AND {played} AND l.person_id IS NOT NULL) AS players
        FROM ehf.venue v
        LEFT JOIN ehf.country ct ON ct.code = v.country_code
        WHERE v.id = %s
        """
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(sql, (venue_id,))
                    row = cursor.fetchone()
        except Error as exc:
            raise DataReadError(f"Could not read venue {venue_id}: {exc}") from exc
        if row is None:
            raise VenueNotFound(venue_id)
        return VenueProfile(
            id=row["id"],
            name=row["name"],
            city=row["city"],
            country_code=row["country_code"],
            country_name=row["country_name"],
            first_match_at=row["first_match_at"],
            last_match_at=row["last_match_at"],
            matches=int(row["matches"] or 0),
            played_matches=int(row["played_matches"] or 0),
            seasons=int(row["seasons"] or 0),
            competitions=int(row["competitions"] or 0),
            teams=int(row["teams"] or 0),
            players=int(row["players"] or 0),
        )

    def fetch_matches(self, venue_id: int, filters: VenueMatchFilters) -> VenueMatchPage:
        extra, extra_params = self._match_where(filters)
        base = MATCH_FROM + extra
        count_sql = f"SELECT COUNT(*) {base}"
        page_sql = (
            f"SELECT m.id, {KICKOFF_AT_SQL} AS kickoff_at, s.code AS season_code, c.name AS competition_name, "
            f"{HOME_NAME} AS home_name, {AWAY_NAME} AS away_name, {SCORE_HOME} AS score_home, "
            f"{SCORE_AWAY} AS score_away, m.result_type {base} "
            f"{order_sql(filters.sort, MATCH_ORDER, 'm.id')} LIMIT %s OFFSET %s"
        )
        params = (venue_id, *extra_params)
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
            raise DataReadError(f"Could not read venue matches {venue_id}: {exc}") from exc
        return VenueMatchPage(tuple(self._match(row) for row in rows), total, filters)

    def fetch_match_options(self, venue_id: int) -> VenueMatchFilterOptions:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    seasons = self._choices(
                        cursor,
                        f"SELECT DISTINCT s.id::text AS value, s.code AS label {MATCH_FROM} ORDER BY s.code DESC",
                        (venue_id,),
                    )
                    competitions = self._choices(
                        cursor,
                        f"SELECT DISTINCT c.id::text AS value, c.name AS label {MATCH_FROM} ORDER BY c.name",
                        (venue_id,),
                    )
                    clubs = self._choices(
                        cursor,
                        f"SELECT club_id::text AS value, MIN(label) AS label FROM ("
                        f"SELECT m.home_club_id AS club_id, {HOME_NAME} AS label {MATCH_FROM} AND m.home_club_id IS NOT NULL "
                        f"UNION ALL "
                        f"SELECT m.away_club_id, {AWAY_NAME} {MATCH_FROM} AND m.away_club_id IS NOT NULL"
                        f") clubs GROUP BY club_id ORDER BY MIN(label)",
                        (venue_id, venue_id),
                    )
        except Error as exc:
            raise DataReadError(f"Could not read venue match filters {venue_id}: {exc}") from exc
        return VenueMatchFilterOptions(seasons, competitions, clubs)

    def fetch_players(self, venue_id: int, filters: VenuePlayerFilters) -> VenuePlayerPage:
        extra, extra_params = self._player_where(filters)
        grouped = (
            f"SELECT p.id, p.display_name, COUNT(DISTINCT l.match_id) AS matches, "
            f"MIN({KICKOFF_AT_SQL}) AS first_at, MAX({KICKOFF_AT_SQL}) AS last_at, SUM(ps.goals) AS goals, "
            f"string_agg(DISTINCT COALESCE(ed.display_name, t.display_name), ', ' "
            f"ORDER BY COALESCE(ed.display_name, t.display_name)) AS teams "
            f"{PLAYER_FROM}{extra} GROUP BY p.id, p.display_name"
        )
        count_sql = f"SELECT COUNT(*) FROM ({grouped}) listed"
        page_sql = (
            f"{grouped} {order_sql(filters.sort, PLAYER_ORDER, 'p.id')} LIMIT %s OFFSET %s"
        )
        params = (venue_id, *extra_params)
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
            raise DataReadError(f"Could not read venue players {venue_id}: {exc}") from exc
        return VenuePlayerPage(tuple(self._player(row) for row in rows), total, filters)

    def fetch_player_ranks(self, venue_id: int) -> tuple[VenuePlayerItem, ...]:
        sql = (
            f"SELECT p.id, p.display_name, COUNT(DISTINCT l.match_id) AS matches, "
            f"MIN({KICKOFF_AT_SQL}) AS first_at, MAX({KICKOFF_AT_SQL}) AS last_at, SUM(ps.goals) AS goals, "
            f"NULL::text AS teams {PLAYER_FROM} GROUP BY p.id, p.display_name"
        )
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(sql, (venue_id,))
                    rows = cursor.fetchall()
        except Error as exc:
            raise DataReadError(f"Could not read venue player ranks {venue_id}: {exc}") from exc
        return tuple(self._player(row) for row in rows)

    def fetch_facts(self, venue_id: int) -> tuple[VenueMatchFact, ...]:
        sql = f"""
        SELECT m.id, {KICKOFF_AT_SQL} AS kickoff_at, s.code AS season_code, s.year_start, c.id AS competition_id,
            c.name AS competition_name, m.home_club_id, m.away_club_id,
            {HOME_NAME} AS home_name, {AWAY_NAME} AS away_name,
            {SCORE_HOME} AS score_home, {SCORE_AWAY} AS score_away, m.result_type, m.spectators
        {MATCH_FROM}
        """
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(sql, (venue_id,))
                    rows = cursor.fetchall()
        except Error as exc:
            raise DataReadError(f"Could not read venue facts {venue_id}: {exc}") from exc
        return tuple(
            VenueMatchFact(
                match_id=row["id"],
                kickoff_at=row["kickoff_at"],
                season_code=row["season_code"],
                year_start=int(row["year_start"] or 0),
                competition_id=row["competition_id"],
                competition_name=row["competition_name"],
                home_club_id=row["home_club_id"],
                away_club_id=row["away_club_id"],
                home_name=row["home_name"],
                away_name=row["away_name"],
                score_home=row["score_home"],
                score_away=row["score_away"],
                result_type=row["result_type"],
                spectators=row["spectators"],
            )
            for row in rows
        )

    def _match_where(self, filters: VenueMatchFilters) -> tuple[str, list[object]]:
        clauses: list[str] = []
        params: list[object] = []
        if filters.season_id is not None:
            clauses.append("s.id = %s")
            params.append(filters.season_id)
        if filters.competition_id is not None:
            clauses.append("c.id = %s")
            params.append(filters.competition_id)
        if filters.club_id is not None:
            clauses.append("(m.home_club_id = %s OR m.away_club_id = %s)")
            params.extend((filters.club_id, filters.club_id))
        if not clauses:
            return "", params
        return " AND " + " AND ".join(clauses), params

    def _player_where(self, filters: VenuePlayerFilters) -> tuple[str, list[object]]:
        if not filters.query:
            return "", []
        return " AND p.display_name ILIKE %s", [f"%{filters.query}%"]

    def _choices(self, cursor, sql: str, params: tuple[object, ...]) -> tuple[Choice, ...]:
        cursor.execute(sql, params)
        return tuple(Choice(row["value"], row["label"]) for row in cursor.fetchall())

    def _match(self, row: dict) -> VenueMatchItem:
        return VenueMatchItem(
            match_id=row["id"],
            kickoff_at=row["kickoff_at"],
            season_code=row["season_code"],
            competition_name=row["competition_name"],
            home_name=row["home_name"],
            away_name=row["away_name"],
            score_home=row["score_home"],
            score_away=row["score_away"],
            result_type=row["result_type"],
        )

    def _player(self, row: dict) -> VenuePlayerItem:
        return VenuePlayerItem(
            player_id=row["id"],
            display_name=row["display_name"] or "—",
            matches=int(row["matches"] or 0),
            first_at=row["first_at"],
            last_at=row["last_at"],
            goals=row["goals"],
            teams=row["teams"],
        )
