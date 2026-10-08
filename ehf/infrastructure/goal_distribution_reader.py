from __future__ import annotations

from collections.abc import Callable

from psycopg import Connection, Error
from psycopg.rows import dict_row

from ehf.domain.errors import DataReadError
from ehf.domain.goal_distribution import (
    GoalDistributionFilters,
    GoalFilterChoices,
    GoalMatch,
    GoalScoreline,
    SeriesKind,
)
from ehf.domain.matches import Choice
from ehf.infrastructure.kickoff import KICKOFF_AT_SQL
from ehf.infrastructure.played import (
    AWAY_NAME,
    EDITION_JOINS,
    HOME_NAME,
    PLAYED_SQL,
    SCORE_AWAY,
    SCORE_HOME,
    TEAM_JOINS,
)

SCORE_PREDICATE = {
    SeriesKind.TOTAL: "score_home + score_away = %s",
    SeriesKind.HOME: "score_home = %s",
    SeriesKind.AWAY: "score_away = %s",
}

FILTER_SQL = """
      AND (%s::int IS NULL OR s.id = %s)
      AND (%s::int IS NULL OR c.id = %s)
      AND (%s::text IS NULL OR c.gender = %s)
"""

SCORELINES_SQL = f"""
SELECT score_home, score_away, COUNT(*)::int AS matches
FROM (
    SELECT
        {SCORE_HOME} AS score_home,
        {SCORE_AWAY} AS score_away
    FROM ehf.match m
    {EDITION_JOINS}
    {TEAM_JOINS}
    WHERE {PLAYED_SQL}
    {FILTER_SQL}
) AS scored
WHERE score_home IS NOT NULL
  AND score_away IS NOT NULL
  AND score_home >= 0
  AND score_away >= 0
GROUP BY score_home, score_away
"""

MATCHES_SQL = {
    kind: f"""
SELECT
    id, kickoff_at, season_code, competition_name, home_name, away_name, score_home, score_away
FROM (
    SELECT
        m.id,
        {KICKOFF_AT_SQL} AS kickoff_at,
        COALESCE(NULLIF(btrim(s.code), ''), '—') AS season_code,
        COALESCE(NULLIF(btrim(c.name), ''), '—') AS competition_name,
        COALESCE(NULLIF(btrim({HOME_NAME}), ''), '—') AS home_name,
        COALESCE(NULLIF(btrim({AWAY_NAME}), ''), '—') AS away_name,
        {SCORE_HOME} AS score_home,
        {SCORE_AWAY} AS score_away
    FROM ehf.match m
    {EDITION_JOINS}
    {TEAM_JOINS}
    WHERE {PLAYED_SQL}
    {FILTER_SQL}
) AS scored
WHERE score_home IS NOT NULL
  AND score_away IS NOT NULL
  AND score_home >= 0
  AND score_away >= 0
  AND {SCORE_PREDICATE[kind]}
ORDER BY kickoff_at DESC NULLS LAST, id DESC
"""
    for kind in SeriesKind
}

SEASONS_SQL = """
SELECT id::text AS value, code AS label
FROM ehf.season
ORDER BY year_start DESC
"""

COMPETITIONS_SQL = """
SELECT id::text AS value, name AS label
FROM ehf.competition
ORDER BY name
"""


class PsycopgGoalDistributionReader:
    def __init__(self, connect: Callable[[], Connection]) -> None:
        self._connect = connect

    def fetch_choices(self) -> GoalFilterChoices:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    seasons = self._choices(cursor, SEASONS_SQL)
                    competitions = self._choices(cursor, COMPETITIONS_SQL)
        except Error as exc:
            raise DataReadError(f"Could not read goal distribution filters: {exc}") from exc
        return GoalFilterChoices(seasons, competitions)

    def fetch_scorelines(self, filters: GoalDistributionFilters) -> tuple[GoalScoreline, ...]:
        params = (
            filters.season_id,
            filters.season_id,
            filters.competition_id,
            filters.competition_id,
            filters.gender,
            filters.gender,
        )
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(SCORELINES_SQL, params)
                    rows = cursor.fetchall()
        except Error as exc:
            raise DataReadError(f"Could not read the goal distribution: {exc}") from exc
        return tuple(
            GoalScoreline(int(row["score_home"]), int(row["score_away"]), int(row["matches"]))
            for row in rows
        )

    def fetch_matches(
        self, filters: GoalDistributionFilters, kind: SeriesKind, goals: int
    ) -> tuple[GoalMatch, ...]:
        params = (
            filters.season_id,
            filters.season_id,
            filters.competition_id,
            filters.competition_id,
            filters.gender,
            filters.gender,
            goals,
        )
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(MATCHES_SQL[kind], params)
                    rows = cursor.fetchall()
        except Error as exc:
            raise DataReadError(f"Could not read matches for the goal distribution: {exc}") from exc
        return tuple(
            GoalMatch(
                match_id=int(row["id"]),
                kickoff=row["kickoff_at"],
                season=str(row["season_code"]),
                competition=str(row["competition_name"]),
                home=str(row["home_name"]),
                away=str(row["away_name"]),
                home_goals=int(row["score_home"]),
                away_goals=int(row["score_away"]),
            )
            for row in rows
        )

    def _choices(self, cursor, sql: str) -> tuple[Choice, ...]:
        cursor.execute(sql)
        return tuple(Choice(value=row["value"], label=row["label"]) for row in cursor.fetchall())
