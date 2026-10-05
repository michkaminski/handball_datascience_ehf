from __future__ import annotations

from collections.abc import Callable, Sequence

from psycopg import Connection, Error
from psycopg.rows import dict_row

from ehf.domain.errors import DataReadError
from ehf.domain.matches import Choice
from ehf.domain.team_report import MatchTeamStats, PreviousStint, TeamReportOptions
from ehf.infrastructure.match_sheet_reader import SEASON_SQL, TEAM_SQL

SEASON_INFO_SQL = """
SELECT s.code,
       p.id AS previous_id,
       p.code AS previous_code
FROM ehf.season s
LEFT JOIN ehf.season p ON p.year_start = s.year_start - 1
WHERE s.id = %(season_id)s
"""

# Lineups of the given people in one season, per club and competition. Goalkeeper numbers skip
# matches where every goalkeeper of both teams has 0 saves (no save data in the import).
PREVIOUS_SQL = """
WITH no_save_data AS (
    SELECT l.match_id
    FROM ehf.match_lineup l
    JOIN ehf.match m ON m.id = l.match_id
    JOIN ehf.competition_edition ce ON ce.id = m.competition_edition_id
    JOIN ehf.match_goalkeeper_stat gk ON gk.lineup_id = l.id
    WHERE ce.season_id = %(season_id)s
    GROUP BY l.match_id
    HAVING SUM(gk.saves) = 0 AND SUM(gk.shots_faced) > 0
)
SELECT
    l.person_id,
    t.club_id,
    COALESCE(MODE() WITHIN GROUP (ORDER BY ed.display_name), MAX(t.display_name), '—') AS club_name,
    c.name AS competition_name,
    COUNT(DISTINCT l.match_id)::int AS matches,
    SUM(ps.goals)::int AS goals,
    SUM(ps.shots)::int AS shots,
    SUM(gk.saves) FILTER (WHERE gk.shots_faced > 0 AND l.match_id NOT IN (SELECT match_id FROM no_save_data))::int AS saves,
    SUM(gk.shots_faced) FILTER (WHERE gk.shots_faced > 0 AND l.match_id NOT IN (SELECT match_id FROM no_save_data))::int AS shots_faced
FROM ehf.match_lineup l
JOIN ehf.match_team t ON t.id = l.match_team_id
JOIN ehf.match m ON m.id = l.match_id
JOIN ehf.competition_edition ce ON ce.id = m.competition_edition_id
JOIN ehf.competition c ON c.id = ce.competition_id
LEFT JOIN ehf.club_edition ed ON ed.club_id = t.club_id AND ed.competition_edition_id = ce.id
LEFT JOIN ehf.match_player_stat ps ON ps.lineup_id = l.id
LEFT JOIN ehf.match_goalkeeper_stat gk ON gk.lineup_id = l.id
WHERE ce.season_id = %(season_id)s AND l.person_id = ANY(%(people)s)
GROUP BY l.person_id, t.club_id, c.name
ORDER BY l.person_id, matches DESC
"""

MATCH_STATS_SQL = """
SELECT
    m.id AS match_id,
    own.shots,
    own.penalty_goals,
    own.penalty_shots,
    own.two_min_suspensions AS two_min,
    other.shots AS opponent_shots
FROM ehf.match m
JOIN ehf.match_team own
    ON own.match_id = m.id
   AND own.side = CASE WHEN m.home_club_id = %(club_id)s THEN 'home' ELSE 'away' END
LEFT JOIN ehf.match_team other ON other.match_id = m.id AND other.side <> own.side
WHERE m.id = ANY(%(matches)s)
"""


class PsycopgTeamReportReader:
    def __init__(self, connect: Callable[[], Connection]) -> None:
        self._connect = connect

    def options(self, season_id: int | None) -> TeamReportOptions:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    seasons = self._choices(cursor, SEASON_SQL, {})
                    chosen = season_id if season_id is not None else (int(seasons[0].value) if seasons else None)
                    teams = (
                        self._choices(cursor, TEAM_SQL, {"season_id": chosen, "competition_id": None})
                        if chosen is not None
                        else ()
                    )
        except Error as exc:
            raise DataReadError(f"Could not read team report options: {exc}") from exc
        return TeamReportOptions(seasons=seasons, teams=teams)

    def season_info(self, season_id: int) -> tuple[str, int | None, str | None]:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(SEASON_INFO_SQL, {"season_id": season_id})
                    row = cursor.fetchone()
        except Error as exc:
            raise DataReadError(f"Could not read season {season_id}: {exc}") from exc
        if row is None:
            raise ValueError(f"Season {season_id} does not exist")
        return row["code"], row["previous_id"], row["previous_code"]

    def previous_stints(self, people: Sequence[int], season_id: int) -> tuple[PreviousStint, ...]:
        if not people:
            return ()
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(PREVIOUS_SQL, {"season_id": season_id, "people": list(people)})
                    return tuple(PreviousStint(**row) for row in cursor.fetchall())
        except Error as exc:
            raise DataReadError(f"Could not read previous season: {exc}") from exc

    def match_stats(self, club_id: int, matches: Sequence[int]) -> dict[int, MatchTeamStats]:
        if not matches:
            return {}
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(MATCH_STATS_SQL, {"club_id": club_id, "matches": list(matches)})
                    return {row["match_id"]: MatchTeamStats(**row) for row in cursor.fetchall()}
        except Error as exc:
            raise DataReadError(f"Could not read match statistics: {exc}") from exc

    @staticmethod
    def _choices(cursor, sql: str, params: dict) -> tuple[Choice, ...]:
        cursor.execute(sql, params)
        return tuple(Choice(value=row["value"], label=row["label"]) for row in cursor.fetchall())
