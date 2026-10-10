from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from psycopg import Connection, Error
from psycopg.rows import dict_row

from ehf.domain.errors import DataReadError
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
from maf.records import MatchRecord

LOCAL_TIME_ZONE = "Europe/Berlin"

MATCHES_SQL = f"""
SELECT
    m.id AS match_id,
    ({KICKOFF_AT_SQL}) AT TIME ZONE '{LOCAL_TIME_ZONE}' AS kickoff,
    s.code AS season,
    s.year_start AS season_order,
    c.key AS competition_key,
    c.name AS competition,
    m.home_club_id AS home_id,
    COALESCE({HOME_NAME}, '—') AS home,
    m.away_club_id AS away_id,
    COALESCE({AWAY_NAME}, '—') AS away,
    m.venue_id AS venue_id,
    NULLIF(concat_ws(', ', NULLIF(btrim(v.name), ''), NULLIF(btrim(v.city), '')), '') AS venue,
    m.spectators AS spectators,
    m.phase AS phase,
    {SCORE_HOME} AS home_goals,
    {SCORE_AWAY} AS away_goals
FROM ehf.match m
{EDITION_JOINS}
{TEAM_JOINS}
LEFT JOIN ehf.venue v ON v.id = m.venue_id
WHERE {PLAYED_SQL}
  AND m.home_club_id IS NOT NULL
  AND m.away_club_id IS NOT NULL
  AND c.gender = %s
ORDER BY m.id
"""

CLUB_NAMES_SQL = """
SELECT DISTINCT ON (ce.club_id) ce.club_id, btrim(ce.display_name) AS name
FROM ehf.club_edition ce
JOIN ehf.competition_edition ed ON ed.id = ce.competition_edition_id
JOIN ehf.season s ON s.id = ed.season_id
WHERE NULLIF(btrim(ce.display_name), '') IS NOT NULL
ORDER BY ce.club_id, s.year_start DESC, ce.id DESC
"""


class PsycopgAttendanceAppealReader:
    def __init__(self, connect: Callable[[], Connection]) -> None:
        self._connect = connect

    def fetch_matches(self, gender: str) -> list[MatchRecord]:
        try:
            with self._connect() as connection:
                connection.read_only = True
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(MATCHES_SQL, (gender,))
                    rows = cursor.fetchall()
                connection.rollback()
        except Error as exc:
            raise DataReadError("Could not read matches for the MAF model.") from exc
        return [_record(row) for row in rows]

    def fetch_club_names(self) -> dict[int, str]:
        try:
            with self._connect() as connection:
                connection.read_only = True
                with connection.cursor() as cursor:
                    cursor.execute(CLUB_NAMES_SQL)
                    rows = cursor.fetchall()
                connection.rollback()
        except Error as exc:
            raise DataReadError("Could not read club names.") from exc
        return {int(row[0]): str(row[1]) for row in rows}


def _optional_int(value: Any) -> int | None:
    return int(value) if value is not None else None


def _record(row: dict[str, Any]) -> MatchRecord:
    kickoff = row["kickoff"]
    return MatchRecord(
        match_id=int(row["match_id"]),
        kickoff=kickoff if isinstance(kickoff, datetime) else None,
        season_key=str(row["season"]),
        season_order=int(row["season_order"] or 0),
        competition_key=str(row["competition_key"]),
        competition_name=str(row["competition"]),
        host_id=int(row["home_id"]),
        host_name=str(row["home"]),
        opponent_id=int(row["away_id"]),
        opponent_name=str(row["away"]),
        venue_id=_optional_int(row["venue_id"]),
        venue_name=row["venue"],
        spectators=_optional_int(row["spectators"]),
        capacity=None,
        phase=row["phase"],
        host_goals=_optional_int(row["home_goals"]),
        opponent_goals=_optional_int(row["away_goals"]),
    )
