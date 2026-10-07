from __future__ import annotations

from collections.abc import Callable, Sequence

from psycopg import Connection, Error
from psycopg.rows import dict_row

from ehf.domain.errors import DataReadError, MatchNotFound
from ehf.domain.match_statistics import LineupEntry
from ehf.domain.match_summary import SummaryHeader, TickerAction, TickerActor

HEADER_SQL = """
SELECT
    m.id,
    ce.competition_id,
    c.name AS competition_name,
    s.code AS season_code,
    s.year_start,
    m.phase,
    m.group_code,
    m.kickoff_at,
    v.name AS venue_name,
    v.city AS venue_city,
    m.spectators,
    COALESCE(home_ed.display_name, home_team.display_name) AS home_name,
    COALESCE(away_ed.display_name, away_team.display_name) AS away_name,
    COALESCE(home_ed.logo_url, home_team.logo_url) AS home_logo,
    COALESCE(away_ed.logo_url, away_team.logo_url) AS away_logo,
    COALESCE(m.score_home, home_team.goals) AS score_home,
    COALESCE(m.score_away, away_team.goals) AS score_away,
    m.half_time_home,
    m.half_time_away,
    COALESCE(m.went_to_extra_time, false) AS extra_time,
    COALESCE(m.went_to_seven_meters, false) AS shootout
FROM ehf.match m
JOIN ehf.competition_edition ce ON ce.id = m.competition_edition_id
JOIN ehf.competition c ON c.id = ce.competition_id
JOIN ehf.season s ON s.id = ce.season_id
LEFT JOIN ehf.venue v ON v.id = m.venue_id
LEFT JOIN ehf.club_edition home_ed
    ON home_ed.club_id = m.home_club_id AND home_ed.competition_edition_id = m.competition_edition_id
LEFT JOIN ehf.club_edition away_ed
    ON away_ed.club_id = m.away_club_id AND away_ed.competition_edition_id = m.competition_edition_id
LEFT JOIN ehf.match_team home_team ON home_team.match_id = m.id AND home_team.side = 'home'
LEFT JOIN ehf.match_team away_team ON away_team.match_id = m.id AND away_team.side = 'away'
WHERE m.id = %s
"""

ACTIONS_SQL = """
SELECT
    a.match_id,
    a.seq,
    a.action_code,
    a.result_code,
    a.shot_zone,
    a.action_add,
    a.period_code,
    a.clock_seconds,
    a.score_home,
    a.score_away,
    p.side,
    p.role_code,
    p.shirt_number,
    COALESCE(p.last_name, p.first_name) AS name,
    p.person_id
FROM ehf.match_action a
LEFT JOIN ehf.match_action_actor p ON p.match_action_id = a.id
WHERE a.match_id = ANY(%s) AND a.clock_seconds IS NOT NULL
ORDER BY a.match_id, a.seq, p.competitor_order NULLS FIRST, p.athlete_order NULLS FIRST, p.id
"""

LINEUP_SQL = """
SELECT
    t.side,
    l.person_id,
    COALESCE(l.shirt_number, '') AS shirt_number,
    COALESCE(
        NULLIF(TRIM(CONCAT_WS(' ', l.first_name, l.last_name)), ''),
        l.display_name,
        l.source_name,
        ''
    ) AS name,
    COALESCE(l.listed_as_goalkeeper, false) AS goalkeeper,
    COALESCE(pe.profile_position, per.profile_position) AS position
FROM ehf.match_lineup l
JOIN ehf.match_team t ON t.id = l.match_team_id
JOIN ehf.match m ON m.id = l.match_id
LEFT JOIN ehf.person per ON per.id = l.person_id
LEFT JOIN LATERAL (
    SELECT pe.profile_position
    FROM ehf.player_edition pe
    WHERE pe.person_id = l.person_id
      AND pe.competition_edition_id = m.competition_edition_id
      AND (t.club_id IS NULL OR pe.club_id = t.club_id)
    ORDER BY pe.id
    LIMIT 1
) pe ON TRUE
WHERE l.match_id = %s
ORDER BY t.side, l.id
"""

# Played matches with a play-by-play feed of one competition, this season and the one before.
REFERENCE_SQL = """
SELECT m.id, s.year_start
FROM ehf.match m
JOIN ehf.competition_edition ce ON ce.id = m.competition_edition_id
JOIN ehf.season s ON s.id = ce.season_id
WHERE ce.competition_id = %(competition_id)s
  AND s.year_start BETWEEN %(year)s - 1 AND %(year)s
  AND m.status = 'played'
  AND EXISTS (SELECT 1 FROM ehf.match_ticker t WHERE t.match_id = m.id)
ORDER BY m.id
"""


class PsycopgMatchSummaryReader:
    def __init__(self, connect: Callable[[], Connection]) -> None:
        self._connect = connect

    def header(self, match_id: int) -> SummaryHeader:
        try:
            with self._connect() as connection, connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(HEADER_SQL, (match_id,))
                row = cursor.fetchone()
        except Error as exc:
            raise DataReadError(f"Could not read match {match_id}: {exc}") from exc
        if row is None:
            raise MatchNotFound(match_id)
        return SummaryHeader(
            match_id=row["id"],
            competition_id=row["competition_id"],
            competition_name=row["competition_name"],
            season_code=row["season_code"],
            year_start=row["year_start"],
            phase=row["phase"],
            group_code=row["group_code"],
            kickoff_at=row["kickoff_at"],
            venue_name=row["venue_name"],
            venue_city=row["venue_city"],
            spectators=row["spectators"],
            home_name=row["home_name"] or "Home",
            away_name=row["away_name"] or "Away",
            home_logo=row["home_logo"],
            away_logo=row["away_logo"],
            score_home=row["score_home"] or 0,
            score_away=row["score_away"] or 0,
            half_time_home=row["half_time_home"],
            half_time_away=row["half_time_away"],
            extra_time=row["extra_time"],
            shootout=row["shootout"],
        )

    def actions(self, match_ids: Sequence[int]) -> dict[int, tuple[TickerAction, ...]]:
        try:
            with self._connect() as connection, connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(ACTIONS_SQL, (list(match_ids),))
                rows = cursor.fetchall()
        except Error as exc:
            raise DataReadError(f"Could not read the play-by-play: {exc}") from exc
        grouped: dict[int, list[TickerAction]] = {}
        current: dict | None = None
        actors: list[TickerActor] = []
        for row in rows:
            if current is None or (row["match_id"], row["seq"]) != (current["match_id"], current["seq"]):
                if current is not None:
                    grouped.setdefault(current["match_id"], []).append(self._action(current, actors))
                current = row
                actors = []
            if row["side"] is not None:
                actors.append(
                    TickerActor(row["side"], row["role_code"], row["shirt_number"], row["name"], row["person_id"])
                )
        if current is not None:
            grouped.setdefault(current["match_id"], []).append(self._action(current, actors))
        return {match_id: tuple(items) for match_id, items in grouped.items()}

    def lineup(self, match_id: int) -> tuple[LineupEntry, ...]:
        try:
            with self._connect() as connection, connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(LINEUP_SQL, (match_id,))
                rows = cursor.fetchall()
        except Error as exc:
            raise DataReadError(f"Could not read the lineup of match {match_id}: {exc}") from exc
        return tuple(
            LineupEntry(
                side=row["side"],
                person_id=row["person_id"],
                number=str(row["shirt_number"]).strip(),
                name=row["name"],
                goalkeeper=row["goalkeeper"],
                position=row["position"],
            )
            for row in rows
            if row["side"] in ("home", "away")
        )

    def reference_matches(self, competition_id: int, year: int) -> dict[int, list[int]]:
        """Match ids per season start year (this season and the previous one)."""
        try:
            with self._connect() as connection, connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(REFERENCE_SQL, {"competition_id": competition_id, "year": year})
                rows = cursor.fetchall()
        except Error as exc:
            raise DataReadError(f"Could not read the reference matches: {exc}") from exc
        seasons: dict[int, list[int]] = {}
        for row in rows:
            seasons.setdefault(row["year_start"], []).append(row["id"])
        return seasons

    @staticmethod
    def _action(row: dict, actors: list[TickerActor]) -> TickerAction:
        return TickerAction(
            seq=row["seq"],
            code=row["action_code"],
            result=row["result_code"],
            zone=row["shot_zone"],
            add=row["action_add"],
            period=row["period_code"],
            seconds=row["clock_seconds"],
            home=row["score_home"],
            away=row["score_away"],
            actors=tuple(actors),
        )
