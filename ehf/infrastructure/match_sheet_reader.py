from __future__ import annotations

from collections.abc import Callable
from datetime import date

from psycopg import Connection, Error
from psycopg.rows import dict_row

from ehf.domain.errors import DataReadError
from ehf.domain.match_sheet import (
    MatchSheetData,
    MatchSheetOptions,
    MatchSheetRequest,
    SheetTeamData,
    SheetVenue,
    SquadEntry,
    SquadPlayer,
    aggregate_squad,
    with_nationalities,
)
from ehf.domain.nationality import nationality_code
from ehf.domain.matches import Choice
from ehf.infrastructure.kickoff import KICKOFF_AT_SQL

SEASON_SQL = """
SELECT s.id::text AS value, s.code AS label
FROM ehf.season s
WHERE EXISTS (
    SELECT 1 FROM ehf.competition_edition ce
    JOIN ehf.club_edition ed ON ed.competition_edition_id = ce.id
    WHERE ce.season_id = s.id
)
ORDER BY s.year_start DESC
"""

COMPETITION_SQL = """
SELECT DISTINCT c.id::text AS value, c.name AS label
FROM ehf.competition_edition ce
JOIN ehf.competition c ON c.id = ce.competition_id
WHERE ce.season_id = %(season_id)s
ORDER BY label
"""

TEAM_SQL = """
SELECT ed.club_id::text AS value,
       MODE() WITHIN GROUP (ORDER BY ed.display_name)
           || COALESCE(' (' || MAX(cl.country_code) || ')', '') AS label
FROM ehf.club_edition ed
JOIN ehf.club cl ON cl.id = ed.club_id
JOIN ehf.competition_edition ce ON ce.id = ed.competition_edition_id
WHERE ce.season_id = %(season_id)s
  AND (%(competition_id)s::bigint IS NULL OR ce.competition_id = %(competition_id)s::bigint)
GROUP BY ed.club_id
ORDER BY label
"""

VENUE_LIST_SQL = """
SELECT DISTINCT v.id::text AS value,
       v.name || COALESCE(', ' || v.city, '') AS label
FROM ehf.match m
JOIN ehf.competition_edition ce ON ce.id = m.competition_edition_id
JOIN ehf.venue v ON v.id = m.venue_id
WHERE ce.season_id = %(season_id)s
ORDER BY label
"""

SEASON_INFO_SQL = """
SELECT s.code,
       (SELECT p.id FROM ehf.season p WHERE p.year_start = s.year_start - 1) AS previous_id,
       COALESCE(
           (SELECT c.name FROM ehf.competition c WHERE c.id = %(competition_id)s::bigint),
           -- no competition chosen: the one both teams play in this season (else the home team's)
           (SELECT c.name
            FROM ehf.club_edition ed
            JOIN ehf.competition_edition ce ON ce.id = ed.competition_edition_id
            JOIN ehf.competition c ON c.id = ce.competition_id
            WHERE ce.season_id = s.id AND ed.club_id IN (%(home_id)s, %(away_id)s)
            GROUP BY c.id, c.name
            ORDER BY COUNT(DISTINCT ed.club_id) DESC, bool_or(ed.club_id = %(home_id)s) DESC, c.name
            LIMIT 1)
       ) AS competition_name
FROM ehf.season s
WHERE s.id = %(season_id)s
"""

CLUB_SQL = """
SELECT cl.id,
       COALESCE(
           (SELECT MODE() WITHIN GROUP (ORDER BY ed.display_name)
            FROM ehf.club_edition ed
            JOIN ehf.competition_edition ce ON ce.id = ed.competition_edition_id
            WHERE ed.club_id = cl.id AND ce.season_id = %(season_id)s),
           (SELECT ed.display_name FROM ehf.club_edition ed WHERE ed.club_id = cl.id ORDER BY ed.id DESC LIMIT 1),
           'Club ' || cl.id
       ) AS name,
       cl.country_code
FROM ehf.club cl
WHERE cl.id = %(club_id)s
"""

VENUE_SQL = """
SELECT v.id, v.name, v.city, v.country_code
FROM ehf.venue v
WHERE v.id = %(venue_id)s
"""

HOME_VENUE_SQL = """
SELECT v.id, v.name, v.city, v.country_code
FROM ehf.match m
JOIN ehf.competition_edition ce ON ce.id = m.competition_edition_id
JOIN ehf.season s ON s.id = ce.season_id
JOIN ehf.venue v ON v.id = m.venue_id
WHERE m.home_club_id = %(club_id)s
GROUP BY v.id, v.name, v.city, v.country_code
ORDER BY COUNT(*) FILTER (WHERE ce.season_id = %(season_id)s) DESC, MAX(s.year_start) DESC, COUNT(*) DESC
LIMIT 1
"""

ENTRY_SQL = f"""
SELECT
    l.match_id,
    l.person_id,
    COALESCE(per.display_name, l.display_name, l.source_name, '—') AS name,
    COALESCE(per.first_name, l.first_name) AS first_name,
    COALESCE(per.last_name, l.last_name) AS last_name,
    l.shirt_number AS number,
    COALESCE(pe.profile_position, per.profile_position) AS position,
    l.listed_as_goalkeeper AS is_goalkeeper,
    EXTRACT(YEAR FROM per.birth_date)::int AS birth_year,
    ps.goals,
    gk.saves,
    gk.shots_faced
FROM ehf.match_lineup l
JOIN ehf.match_team t ON t.id = l.match_team_id
JOIN ehf.match m ON m.id = l.match_id
JOIN ehf.competition_edition ce ON ce.id = m.competition_edition_id
LEFT JOIN ehf.person per ON per.id = l.person_id
LEFT JOIN LATERAL (
    SELECT pe.profile_position
    FROM ehf.player_edition pe
    WHERE pe.person_id = l.person_id
      AND pe.competition_edition_id = m.competition_edition_id
      AND pe.club_id = %(club_id)s
    ORDER BY pe.id
    LIMIT 1
) pe ON TRUE
LEFT JOIN ehf.match_player_stat ps ON ps.lineup_id = l.id
LEFT JOIN ehf.match_goalkeeper_stat gk ON gk.lineup_id = l.id
WHERE ce.season_id = %(season_id)s
  AND t.side = CASE WHEN m.home_club_id = %(club_id)s THEN 'home'
                    WHEN m.away_club_id = %(club_id)s THEN 'away' END
  AND (%(until)s::date IS NULL OR ({KICKOFF_AT_SQL})::date < %(until)s::date)
ORDER BY {KICKOFF_AT_SQL} DESC NULLS LAST, l.match_id DESC, l.id
"""

NO_SAVE_DATA_SQL = """
SELECT l.match_id
FROM ehf.match_lineup l
JOIN ehf.match m ON m.id = l.match_id
JOIN ehf.competition_edition ce ON ce.id = m.competition_edition_id
JOIN ehf.match_goalkeeper_stat gk ON gk.lineup_id = l.id
WHERE ce.season_id = ANY(%(seasons)s)
  AND %(club_id)s IN (m.home_club_id, m.away_club_id)
GROUP BY l.match_id
HAVING SUM(gk.saves) = 0 AND SUM(gk.shots_faced) > 0
"""

ROSTER_SQL = """
SELECT DISTINCT ON (per.id)
    per.id AS person_id,
    per.display_name AS name,
    per.first_name,
    per.last_name,
    NULL::text AS number,
    COALESCE(pe.profile_position, per.profile_position) AS position,
    COALESCE(pe.profile_position, per.profile_position) ILIKE 'goalkeeper' AS is_goalkeeper,
    EXTRACT(YEAR FROM per.birth_date)::int AS birth_year,
    NULL::int AS matches,
    NULL::int AS goals,
    NULL::int AS saves,
    NULL::int AS shots_faced
FROM ehf.player_edition pe
JOIN ehf.person per ON per.id = pe.person_id
JOIN ehf.competition_edition ce ON ce.id = pe.competition_edition_id
WHERE pe.club_id = %(club_id)s AND ce.season_id = %(season_id)s
ORDER BY per.id, pe.id
"""

NATIONALITY_SQL = """
SELECT n.person_id, n.nationality, co.code
FROM ehf.person_nationality n
LEFT JOIN ehf.country co ON lower(co.name) = lower(n.nationality)
WHERE n.person_id = ANY(%(people)s)
ORDER BY n.person_id, n.nationality
"""


class PsycopgMatchSheetReader:
    def __init__(self, connect: Callable[[], Connection]) -> None:
        self._connect = connect

    def options(self, season_id: int | None, competition_id: int | None) -> MatchSheetOptions:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    seasons = self._choices(cursor, SEASON_SQL, {})
                    chosen = season_id if season_id is not None else (int(seasons[0].value) if seasons else None)
                    if chosen is None:
                        return MatchSheetOptions(seasons=seasons, competitions=(), teams=(), venues=())
                    params = {"season_id": chosen, "competition_id": competition_id}
                    return MatchSheetOptions(
                        seasons=seasons,
                        competitions=self._choices(cursor, COMPETITION_SQL, params),
                        teams=self._choices(cursor, TEAM_SQL, params),
                        venues=self._choices(cursor, VENUE_LIST_SQL, params),
                    )
        except Error as exc:
            raise DataReadError(f"Could not read match sheet options: {exc}") from exc

    def teams(self, season_id: int, competition_id: int | None) -> tuple[Choice, ...]:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    return self._choices(cursor, TEAM_SQL, {"season_id": season_id, "competition_id": competition_id})
        except Error as exc:
            raise DataReadError(f"Could not read teams: {exc}") from exc

    def fetch(self, request: MatchSheetRequest) -> MatchSheetData:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        SEASON_INFO_SQL,
                        {
                            "season_id": request.season_id,
                            "competition_id": request.competition_id,
                            "home_id": request.home_id,
                            "away_id": request.away_id,
                        },
                    )
                    season = cursor.fetchone()
                    if season is None:
                        raise ValueError(f"Season {request.season_id} does not exist")
                    home = self._team(cursor, request.home_id, request, season["previous_id"])
                    away = self._team(cursor, request.away_id, request, season["previous_id"])
                    venue = self._venue(cursor, request)
        except Error as exc:
            raise DataReadError(f"Could not read match sheet data: {exc}") from exc
        return MatchSheetData(
            season_code=season["code"],
            competition_name=season["competition_name"],
            home=home,
            away=away,
            venue=venue,
            stats_until=request.match_date,
        )

    def _team(self, cursor, club_id: int, request: MatchSheetRequest, previous_id: int | None) -> SheetTeamData:
        cursor.execute(CLUB_SQL, {"club_id": club_id, "season_id": request.season_id})
        club = cursor.fetchone()
        if club is None:
            raise ValueError(f"Team {club_id} does not exist")
        seasons = [request.season_id] + ([previous_id] if previous_id else [])
        cursor.execute(NO_SAVE_DATA_SQL, {"club_id": club_id, "seasons": seasons})
        no_save_data = frozenset(row["match_id"] for row in cursor.fetchall())
        current = self._squad(cursor, club_id, request.season_id, request.match_date, no_save_data)
        previous = (
            self._squad(cursor, club_id, previous_id, None, no_save_data)
            if request.previous_season and previous_id
            else ()
        )
        roster: tuple[SquadPlayer, ...] = ()
        if not current:
            cursor.execute(ROSTER_SQL, {"club_id": club_id, "season_id": request.season_id})
            roster = tuple(SquadPlayer(**row) for row in cursor.fetchall())
        codes = self._nationalities(cursor, current, previous, roster)
        return SheetTeamData(
            club_id=club["id"],
            name=club["name"],
            country_code=club["country_code"],
            current=with_nationalities(current, codes),
            previous=with_nationalities(previous, codes),
            roster=with_nationalities(roster, codes),
        )

    @staticmethod
    def _nationalities(cursor, *groups: tuple[SquadPlayer, ...]) -> dict[int, tuple[str, ...]]:
        people = list({player.person_id for group in groups for player in group if player.person_id is not None})
        if not people:
            return {}
        cursor.execute(NATIONALITY_SQL, {"people": people})
        grouped: dict[int, list[str]] = {}
        for row in cursor.fetchall():
            code = nationality_code(row["nationality"], row["code"])
            codes = grouped.setdefault(row["person_id"], [])
            if code not in codes:
                codes.append(code)
        return {person: tuple(codes) for person, codes in grouped.items()}

    @staticmethod
    def _squad(cursor, club_id: int, season_id: int, until: date | None, no_save_data: frozenset[int]):
        cursor.execute(ENTRY_SQL, {"club_id": club_id, "season_id": season_id, "until": until})
        entries = tuple(SquadEntry(**row) for row in cursor.fetchall())
        return aggregate_squad(entries, no_save_data)

    @staticmethod
    def _venue(cursor, request: MatchSheetRequest) -> SheetVenue | None:
        if request.venue_id is not None:
            cursor.execute(VENUE_SQL, {"venue_id": request.venue_id})
        else:
            cursor.execute(HOME_VENUE_SQL, {"club_id": request.home_id, "season_id": request.season_id})
        row = cursor.fetchone()
        return None if row is None else SheetVenue(**row)

    @staticmethod
    def _choices(cursor, sql: str, params: dict) -> tuple[Choice, ...]:
        cursor.execute(sql, params)
        return tuple(Choice(value=row["value"], label=row["label"]) for row in cursor.fetchall())
