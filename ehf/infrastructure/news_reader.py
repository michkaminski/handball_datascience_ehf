from __future__ import annotations

from collections.abc import Callable

from psycopg import Connection, Error
from psycopg.rows import dict_row

from ehf.domain.errors import DataReadError
from ehf.domain.matches import MatchListItem
from ehf.domain.news import (
    NewsCompetition,
    NewsGoalkeeper,
    NewsPerformance,
    NewsResultMatch,
    NewsScorer,
    NewsSeason,
    UpcomingSection,
)
from ehf.infrastructure.kickoff import KICKOFF_AT_SQL
from ehf.infrastructure.played import EDITION_JOINS, HOME_NAME, AWAY_NAME, PLAYED_SQL, SCORE_HOME, SCORE_AWAY, TEAM_JOINS

MATCHES_PER_SECTION = 6
SCORERS_PER_COMPETITION = 5
GOALKEEPERS_PER_COMPETITION = 5
BEST_PERFORMANCES_LIMIT = 3
UPCOMING_PER_COMPETITION = 6
TEAM_NAME = "COALESCE(ed.display_name, t.display_name)"


class PsycopgNewsReader:
    def __init__(self, connect: Callable[[], Connection]) -> None:
        self._connect = connect

    def fetch_current_season(self) -> NewsSeason | None:
        sql = f"""
SELECT s.id, s.code
FROM ehf.season s
WHERE EXISTS (
    SELECT 1
    FROM ehf.match m
    JOIN ehf.competition_edition ce ON ce.id = m.competition_edition_id
    WHERE ce.season_id = s.id AND {PLAYED_SQL}
)
ORDER BY s.year_start DESC, s.id DESC
LIMIT 1
"""
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(sql)
                    row = cursor.fetchone()
        except Error as exc:
            raise DataReadError(f"Could not read current EHF season: {exc}") from exc
        if not row:
            return None
        return NewsSeason(id=row["id"], code=row["code"])

    def fetch_competitions(self, season_id: int) -> tuple[NewsCompetition, ...]:
        sql = """
SELECT DISTINCT c.id, c.key, c.name
FROM ehf.competition c
JOIN ehf.competition_edition ce ON ce.competition_id = c.id
WHERE ce.season_id = %s
ORDER BY c.name
"""
        return self._competitions(sql, (season_id,))

    def fetch_played_matches(self, season_id: int) -> tuple[NewsResultMatch, ...]:
        sql = f"""
SELECT
    m.id,
    {KICKOFF_AT_SQL} AS kickoff_at,
    c.id AS competition_id,
    {HOME_NAME} AS home_name,
    {AWAY_NAME} AS away_name,
    {SCORE_HOME} AS score_home,
    {SCORE_AWAY} AS score_away,
    m.result_type
FROM ehf.match m
{EDITION_JOINS}
{TEAM_JOINS}
WHERE s.id = %s AND {PLAYED_SQL}
ORDER BY {KICKOFF_AT_SQL} DESC NULLS LAST, m.id DESC
"""
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(sql, (season_id,))
                    rows = cursor.fetchall()
        except Error as exc:
            raise DataReadError(f"Could not read played matches for news: {exc}") from exc
        return tuple(self._result_match(row) for row in rows)

    def fetch_top_scorers(self, season_id: int, limit: int = SCORERS_PER_COMPETITION) -> tuple[NewsScorer, ...]:
        sql = f"""
WITH scored AS (
    SELECT
        c.id AS competition_id,
        p.id AS player_id,
        p.display_name AS player_name,
        MIN({TEAM_NAME}) AS team,
        COUNT(DISTINCT m.id)::int AS matches,
        SUM(COALESCE(ps.goals, 0))::int AS goals,
        ROW_NUMBER() OVER (
            PARTITION BY c.id
            ORDER BY SUM(COALESCE(ps.goals, 0)) DESC, COUNT(DISTINCT m.id), p.display_name
        ) AS position
    FROM ehf.match_lineup l
    JOIN ehf.match_team t ON t.id = l.match_team_id
    JOIN ehf.match m ON m.id = t.match_id
    {EDITION_JOINS}
    LEFT JOIN ehf.club_edition ed
        ON ed.club_id = t.club_id
       AND ed.competition_edition_id = m.competition_edition_id
    JOIN ehf.match_player_stat ps ON ps.lineup_id = l.id
    JOIN ehf.person p ON p.id = l.person_id
    WHERE s.id = %s
      AND l.person_id IS NOT NULL
      AND {PLAYED_SQL}
    GROUP BY c.id, p.id, p.display_name
)
SELECT competition_id, player_id, player_name, team, matches, goals
FROM scored
WHERE position <= %s AND goals > 0
ORDER BY competition_id, position
"""
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(sql, (season_id, limit))
                    rows = cursor.fetchall()
        except Error as exc:
            raise DataReadError(f"Could not read news scorers: {exc}") from exc
        return tuple(
            NewsScorer(
                competition_id=row["competition_id"],
                player_id=row["player_id"],
                player_name=row["player_name"],
                team=row["team"],
                matches=row["matches"],
                goals=row["goals"],
            )
            for row in rows
        )

    def fetch_top_goalkeepers(
        self, season_id: int, limit: int = GOALKEEPERS_PER_COMPETITION
    ) -> tuple[NewsGoalkeeper, ...]:
        sql = f"""
WITH ranked AS (
    SELECT
        c.id AS competition_id,
        p.id AS player_id,
        p.display_name AS player_name,
        MIN({TEAM_NAME}) AS team,
        COUNT(DISTINCT m.id)::int AS matches,
        SUM(COALESCE(gk.shots_faced, 0))::int AS shots_faced,
        SUM(COALESCE(gk.saves, 0))::int AS saves,
        AVG(gk.save_percentage)::float AS average_save_percentage,
        ROW_NUMBER() OVER (
            PARTITION BY c.id
            ORDER BY AVG(gk.save_percentage) DESC, COUNT(DISTINCT m.id) DESC, p.display_name
        ) AS position
    FROM ehf.match_lineup l
    JOIN ehf.match_goalkeeper_stat gk ON gk.lineup_id = l.id
    JOIN ehf.match_team t ON t.id = l.match_team_id
    JOIN ehf.match m ON m.id = t.match_id
    {EDITION_JOINS}
    LEFT JOIN ehf.club_edition ed
        ON ed.club_id = t.club_id
       AND ed.competition_edition_id = m.competition_edition_id
    JOIN ehf.person p ON p.id = l.person_id
    WHERE s.id = %s
      AND l.person_id IS NOT NULL
      AND {PLAYED_SQL}
      AND gk.save_percentage IS NOT NULL
    GROUP BY c.id, p.id, p.display_name
)
SELECT competition_id, player_id, player_name, team, matches, shots_faced, saves, average_save_percentage
FROM ranked
WHERE position <= %s AND matches > 0
ORDER BY competition_id, position
"""
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(sql, (season_id, limit))
                    rows = cursor.fetchall()
        except Error as exc:
            raise DataReadError(f"Could not read news goalkeepers: {exc}") from exc
        return tuple(
            NewsGoalkeeper(
                competition_id=row["competition_id"],
                player_id=row["player_id"],
                player_name=row["player_name"],
                team=row["team"],
                matches=row["matches"],
                shots_faced=row["shots_faced"],
                saves=row["saves"],
                average_save_percentage=float(row["average_save_percentage"]),
            )
            for row in rows
        )

    def fetch_best_performances(
        self, season_id: int, limit: int = BEST_PERFORMANCES_LIMIT
    ) -> tuple[NewsPerformance, ...]:
        sql = f"""
SELECT
    c.id AS competition_id,
    m.id AS match_id,
    {KICKOFF_AT_SQL} AS kickoff_at,
    p.id AS player_id,
    p.display_name AS player_name,
    MIN({TEAM_NAME}) AS team,
    SUM(COALESCE(ps.goals, 0))::int AS goals
FROM ehf.match_lineup l
JOIN ehf.match_team t ON t.id = l.match_team_id
JOIN ehf.match m ON m.id = t.match_id
{EDITION_JOINS}
LEFT JOIN ehf.club_edition ed
    ON ed.club_id = t.club_id
   AND ed.competition_edition_id = m.competition_edition_id
JOIN ehf.match_player_stat ps ON ps.lineup_id = l.id
JOIN ehf.person p ON p.id = l.person_id
WHERE s.id = %s
  AND l.person_id IS NOT NULL
  AND {PLAYED_SQL}
GROUP BY c.id, m.id, {KICKOFF_AT_SQL}, p.id, p.display_name
HAVING SUM(COALESCE(ps.goals, 0)) > 0
ORDER BY goals DESC, {KICKOFF_AT_SQL} DESC NULLS LAST, m.id DESC
LIMIT %s
"""
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(sql, (season_id, limit))
                    rows = cursor.fetchall()
        except Error as exc:
            raise DataReadError(f"Could not read best performances for news: {exc}") from exc
        return tuple(
            NewsPerformance(
                competition_id=row["competition_id"],
                match_id=row["match_id"],
                kickoff_at=row["kickoff_at"],
                player_id=row["player_id"],
                player_name=row["player_name"],
                team=row["team"],
                goals=row["goals"],
            )
            for row in rows
        )

    def fetch_upcoming_sections(
        self,
        season_id: int | None = None,
        limit: int = UPCOMING_PER_COMPETITION,
    ) -> tuple[UpcomingSection, ...]:
        season_filter = "AND ce.season_id = %s" if season_id is not None else ""
        params: list[object] = []
        if season_id is not None:
            params.append(season_id)
        params.append(limit)
        latest_season = """
AND ce.season_id = (
    SELECT ce_inner.season_id
    FROM ehf.competition_edition ce_inner
    JOIN ehf.season s_inner ON s_inner.id = ce_inner.season_id
    WHERE ce_inner.competition_id = c.id
    ORDER BY s_inner.year_start DESC, ce_inner.id DESC
    LIMIT 1
)
"""
        sql = f"""
WITH ranked AS (
    SELECT
        m.id,
        {KICKOFF_AT_SQL} AS kickoff_at,
        s.code AS season_code,
        s.id AS season_id,
        c.name AS competition_name,
        c.id AS competition_id,
        c.key AS competition_key,
        {HOME_NAME} AS home_name,
        {AWAY_NAME} AS away_name,
        {SCORE_HOME} AS score_home,
        {SCORE_AWAY} AS score_away,
        m.result_type,
        m.status,
        v.name AS venue_name,
        m.spectators,
        m.phase,
        m.group_code,
        ROW_NUMBER() OVER (
            PARTITION BY c.id
            ORDER BY {KICKOFF_AT_SQL} NULLS LAST, m.id
        ) AS position
    FROM ehf.match m
    JOIN ehf.competition_edition ce ON ce.id = m.competition_edition_id
    JOIN ehf.season s ON s.id = ce.season_id
    JOIN ehf.competition c ON c.id = ce.competition_id
    {TEAM_JOINS}
    LEFT JOIN ehf.venue v ON v.id = m.venue_id
    WHERE m.status = 'scheduled_or_no_result'
      {season_filter}
      {'' if season_id is not None else latest_season}
      AND (
          {KICKOFF_AT_SQL} IS NULL
          OR {KICKOFF_AT_SQL}::date >= CURRENT_DATE
      )
)
SELECT *
FROM ranked
WHERE position <= %s
ORDER BY competition_name, position
"""
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(sql, tuple(params))
                    rows = cursor.fetchall()
        except Error as exc:
            raise DataReadError(f"Could not read upcoming matches for news: {exc}") from exc
        sections: dict[int, UpcomingSection] = {}
        items: dict[int, list[MatchListItem]] = {}
        competitions: dict[int, NewsCompetition] = {}
        for row in rows:
            competition_id = row["competition_id"]
            if competition_id not in competitions:
                competitions[competition_id] = NewsCompetition(
                    id=competition_id,
                    key=row["competition_key"],
                    name=row["competition_name"],
                )
                items[competition_id] = []
            items[competition_id].append(self._list_item(row))
        for competition_id, competition in competitions.items():
            sections[competition_id] = UpcomingSection(
                competition=competition,
                matches=tuple(items[competition_id]),
            )
        return tuple(
            sections[competition_id]
            for competition_id in sorted(
                sections,
                key=lambda cid: sections[cid].competition.sort_rank,
            )
        )

    def _competitions(self, sql: str, params: tuple[object, ...]) -> tuple[NewsCompetition, ...]:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(sql, params)
                    rows = cursor.fetchall()
        except Error as exc:
            raise DataReadError(f"Could not read competitions for news: {exc}") from exc
        return tuple(
            NewsCompetition(id=row["id"], key=row["key"], name=row["name"]) for row in rows
        )

    @staticmethod
    def _result_match(row: dict) -> NewsResultMatch:
        return NewsResultMatch(
            id=row["id"],
            kickoff_at=row["kickoff_at"],
            competition_id=row["competition_id"],
            home_name=row["home_name"],
            away_name=row["away_name"],
            score_home=row["score_home"],
            score_away=row["score_away"],
            result_type=row["result_type"],
        )

    @staticmethod
    def _list_item(row: dict) -> MatchListItem:
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
            spectators=row["spectators"],
            phase=row["phase"],
            group_code=row["group_code"],
        )
