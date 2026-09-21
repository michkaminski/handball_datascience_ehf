from __future__ import annotations

from collections.abc import Callable

from psycopg import Connection, Error
from psycopg.rows import dict_row

from ehf.domain.errors import DataReadError, RefereeNotFound
from ehf.domain.matches import Choice
from ehf.domain.referees import (
    RefereeMatchFact,
    RefereeMatchFilterOptions,
    RefereeMatchFilters,
    RefereeMatchItem,
    RefereeMatchPage,
    RefereeProfile,
    RefereeSeasonRow,
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

SAME_PERSON = """
o.display_name IS NOT DISTINCT FROM seed.display_name
AND o.first_name IS NOT DISTINCT FROM seed.first_name
AND o.last_name IS NOT DISTINCT FROM seed.last_name
AND o.country_code IS NOT DISTINCT FROM seed.country_code
"""

SEED = "SELECT display_name, first_name, last_name, country_code, source_name FROM ehf.match_official WHERE id = %s AND role = 'referee'"

PARTNER_ID = f"""
(
    SELECT MIN(allp.id)
    FROM ehf.match_official partner
    JOIN ehf.match_official allp
      ON allp.role = 'referee'
     AND allp.display_name IS NOT DISTINCT FROM partner.display_name
     AND allp.first_name IS NOT DISTINCT FROM partner.first_name
     AND allp.last_name IS NOT DISTINCT FROM partner.last_name
     AND allp.country_code IS NOT DISTINCT FROM partner.country_code
    JOIN seed ON TRUE
    WHERE partner.match_id = m.id AND partner.role = 'referee'
      AND NOT (
          partner.display_name IS NOT DISTINCT FROM seed.display_name
      AND partner.first_name IS NOT DISTINCT FROM seed.first_name
      AND partner.last_name IS NOT DISTINCT FROM seed.last_name
      AND partner.country_code IS NOT DISTINCT FROM seed.country_code
      )
)
"""

PARTNER_NAME = """
(
    SELECT COALESCE(partner.display_name, NULLIF(TRIM(BOTH FROM CONCAT_WS(' ', partner.first_name, partner.last_name)), ''), partner.source_name)
    FROM ehf.match_official partner
    JOIN seed ON TRUE
    WHERE partner.match_id = m.id AND partner.role = 'referee'
      AND NOT (
          partner.display_name IS NOT DISTINCT FROM seed.display_name
      AND partner.first_name IS NOT DISTINCT FROM seed.first_name
      AND partner.last_name IS NOT DISTINCT FROM seed.last_name
      AND partner.country_code IS NOT DISTINCT FROM seed.country_code
      )
    LIMIT 1
)
"""

MATCH_FROM = f"""
FROM ehf.match_official o
JOIN seed ON {SAME_PERSON}
JOIN ehf.match m ON m.id = o.match_id
{EDITION_JOINS}
{TEAM_JOINS}
WHERE o.role = 'referee'
"""


class PsycopgRefereeDetailReader:
    def __init__(self, connect: Callable[[], Connection]) -> None:
        self._connect = connect

    def fetch_profile(self, referee_id: int) -> RefereeProfile:
        sql = f"""
        WITH seed AS ({SEED})
        SELECT MIN(o.id) AS id,
            MAX(o.display_name) AS display_name,
            MAX(o.first_name) AS first_name,
            MAX(o.last_name) AS last_name,
            MAX(o.source_name) AS source_name,
            MAX(o.country_code) AS country_code,
            MAX(ct.name) AS country_name,
            MIN({KICKOFF_AT_SQL}) AS first_match_at,
            MAX({KICKOFF_AT_SQL}) AS last_match_at,
            COUNT(DISTINCT o.match_id) AS matches,
            COUNT(DISTINCT o.match_id) FILTER (WHERE {PLAYED_SQL}) AS played_matches,
            COUNT(DISTINCT ce.season_id) AS seasons,
            COUNT(DISTINCT ce.competition_id) AS competitions
        FROM ehf.match_official o
        JOIN seed ON {SAME_PERSON}
        JOIN ehf.match m ON m.id = o.match_id
        JOIN ehf.competition_edition ce ON ce.id = m.competition_edition_id
        LEFT JOIN ehf.country ct ON ct.code = o.country_code
        WHERE o.role = 'referee'
        """
        activity_sql = f"""
        WITH seed AS ({SEED})
        SELECT s.code AS season_code, COUNT(DISTINCT o.match_id) AS matches,
            string_agg(DISTINCT c.name, ', ' ORDER BY c.name) AS competitions
        FROM ehf.match_official o
        JOIN seed ON {SAME_PERSON}
        JOIN ehf.match m ON m.id = o.match_id
        JOIN ehf.competition_edition ce ON ce.id = m.competition_edition_id
        JOIN ehf.season s ON s.id = ce.season_id
        JOIN ehf.competition c ON c.id = ce.competition_id
        WHERE o.role = 'referee'
        GROUP BY s.code, s.year_start
        ORDER BY s.year_start DESC
        """
        teams_sql = f"""
        WITH seed AS ({SEED})
        SELECT COUNT(*) FROM (
            SELECT m.home_club_id AS club_id
            FROM ehf.match_official o
            JOIN seed ON {SAME_PERSON}
            JOIN ehf.match m ON m.id = o.match_id
            WHERE o.role = 'referee' AND m.home_club_id IS NOT NULL
            UNION
            SELECT m.away_club_id
            FROM ehf.match_official o
            JOIN seed ON {SAME_PERSON}
            JOIN ehf.match m ON m.id = o.match_id
            WHERE o.role = 'referee' AND m.away_club_id IS NOT NULL
        ) clubs
        """
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(sql, (referee_id,))
                    row = cursor.fetchone()
                    if row is None or row["id"] is None:
                        raise RefereeNotFound(referee_id)
                    cursor.execute(activity_sql, (referee_id,))
                    activity = cursor.fetchall()
                with connection.cursor() as cursor:
                    cursor.execute(teams_sql, (referee_id,))
                    teams = int(cursor.fetchone()[0])
        except RefereeNotFound:
            raise
        except Error as exc:
            raise DataReadError(f"Could not read referee {referee_id}: {exc}") from exc
        return RefereeProfile(
            id=row["id"],
            display_name=row["display_name"] or row["last_name"] or row["first_name"] or row["source_name"] or "—",
            first_name=row["first_name"],
            last_name=row["last_name"],
            source_name=row["source_name"],
            country_code=row["country_code"],
            country_name=row["country_name"],
            first_match_at=row["first_match_at"],
            last_match_at=row["last_match_at"],
            matches=int(row["matches"] or 0),
            played_matches=int(row["played_matches"] or 0),
            seasons=int(row["seasons"] or 0),
            competitions=int(row["competitions"] or 0),
            teams=teams,
            seasons_activity=tuple(
                RefereeSeasonRow(item["season_code"], int(item["matches"] or 0), item["competitions"])
                for item in activity
            ),
        )

    def fetch_matches(self, referee_id: int, filters: RefereeMatchFilters) -> RefereeMatchPage:
        extra, extra_params = self._match_where(filters)
        count_sql = f"WITH seed AS ({SEED}) SELECT COUNT(DISTINCT m.id) {MATCH_FROM}{extra}"
        page_sql = (
            f"WITH seed AS ({SEED}), listed AS ("
            f"SELECT DISTINCT m.id, {KICKOFF_AT_SQL} AS kickoff_at, s.code AS season_code, c.name AS competition_name, "
            f"{HOME_NAME} AS home_name, {AWAY_NAME} AS away_name, {SCORE_HOME} AS score_home, "
            f"{SCORE_AWAY} AS score_away, m.result_type, {PARTNER_ID} AS partner_id, "
            f"{PARTNER_NAME} AS partner_name {MATCH_FROM}{extra}"
            f") SELECT * FROM listed {order_sql(filters.sort, self._listed_order(), 'id')} LIMIT %s OFFSET %s"
        )
        params = (referee_id, *extra_params)
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(count_sql, (referee_id, *extra_params))
                    total = int(cursor.fetchone()[0])
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        page_sql,
                        (*params, filters.page_size, (filters.page - 1) * filters.page_size),
                    )
                    rows = cursor.fetchall()
        except Error as exc:
            raise DataReadError(f"Could not read referee matches {referee_id}: {exc}") from exc
        return RefereeMatchPage(tuple(self._match(row) for row in rows), total, filters)

    def fetch_match_options(self, referee_id: int) -> RefereeMatchFilterOptions:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    seasons = self._choices(
                        cursor,
                        f"WITH seed AS ({SEED}) SELECT DISTINCT s.id::text AS value, s.code AS label "
                        f"{MATCH_FROM} ORDER BY s.code DESC",
                        (referee_id,),
                    )
                    competitions = self._choices(
                        cursor,
                        f"WITH seed AS ({SEED}) SELECT DISTINCT c.id::text AS value, c.name AS label "
                        f"{MATCH_FROM} ORDER BY c.name",
                        (referee_id,),
                    )
                    clubs = self._choices(
                        cursor,
                        f"WITH seed AS ({SEED}) SELECT club_id::text AS value, MIN(label) AS label FROM ("
                        f"SELECT m.home_club_id AS club_id, {HOME_NAME} AS label {MATCH_FROM} AND m.home_club_id IS NOT NULL "
                        f"UNION ALL "
                        f"SELECT m.away_club_id, {AWAY_NAME} {MATCH_FROM} AND m.away_club_id IS NOT NULL"
                        f") clubs GROUP BY club_id ORDER BY MIN(label)",
                        (referee_id,),
                    )
        except Error as exc:
            raise DataReadError(f"Could not read referee match filters {referee_id}: {exc}") from exc
        return RefereeMatchFilterOptions(seasons, competitions, clubs)

    def fetch_facts(self, referee_id: int) -> tuple[RefereeMatchFact, ...]:
        sql = (
            f"WITH seed AS ({SEED}) SELECT DISTINCT m.id, {KICKOFF_AT_SQL} AS kickoff_at, s.code AS season_code, "
            f"s.year_start, c.id AS competition_id, c.name AS competition_name, "
            f"m.home_club_id, m.away_club_id, {HOME_NAME} AS home_name, {AWAY_NAME} AS away_name, "
            f"{PARTNER_ID} AS partner_id, {PARTNER_NAME} AS partner_name "
            f"{MATCH_FROM} AND {PLAYED_SQL}"
        )
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(sql, (referee_id,))
                    rows = cursor.fetchall()
        except Error as exc:
            raise DataReadError(f"Could not read referee facts {referee_id}: {exc}") from exc
        return tuple(
            RefereeMatchFact(
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
                partner_id=row["partner_id"],
                partner_name=row["partner_name"],
            )
            for row in rows
        )

    def _match_where(self, filters: RefereeMatchFilters) -> tuple[str, list[object]]:
        clauses: list[str] = []
        params: list[object] = []
        if filters.season_id is not None:
            clauses.append("s.id = %s")
            params.append(filters.season_id)
        if filters.competition_id is not None:
            clauses.append("c.id = %s")
            params.append(filters.competition_id)
        if filters.club_id is not None and filters.side == "home":
            clauses.append("m.home_club_id = %s")
            params.append(filters.club_id)
        elif filters.club_id is not None and filters.side == "away":
            clauses.append("m.away_club_id = %s")
            params.append(filters.club_id)
        elif filters.club_id is not None:
            clauses.append("(m.home_club_id = %s OR m.away_club_id = %s)")
            params.extend((filters.club_id, filters.club_id))
        if filters.date_from is not None:
            clauses.append(f"{KICKOFF_AT_SQL}::date >= %s")
            params.append(filters.date_from)
        if filters.date_to is not None:
            clauses.append(f"{KICKOFF_AT_SQL}::date <= %s")
            params.append(filters.date_to)
        if not clauses:
            return "", params
        return " AND " + " AND ".join(clauses), params

    def _listed_order(self) -> dict[str, tuple[str, ...]]:
        return {
            "date": ("kickoff_at",),
            "season": ("season_code",),
            "competition": ("competition_name",),
            "home": ("home_name",),
            "score": ("score_home", "score_away"),
            "away": ("away_name",),
            "partner": ("partner_name",),
        }

    def _choices(self, cursor, sql: str, params: tuple[object, ...]) -> tuple[Choice, ...]:
        cursor.execute(sql, params)
        return tuple(Choice(row["value"], row["label"]) for row in cursor.fetchall())

    def _match(self, row: dict) -> RefereeMatchItem:
        return RefereeMatchItem(
            match_id=row["id"],
            kickoff_at=row["kickoff_at"],
            season_code=row["season_code"],
            competition_name=row["competition_name"],
            home_name=row["home_name"],
            away_name=row["away_name"],
            score_home=row["score_home"],
            score_away=row["score_away"],
            result_type=row["result_type"],
            partner_id=row["partner_id"],
            partner_name=row["partner_name"],
        )
