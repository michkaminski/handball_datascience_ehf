from __future__ import annotations

from collections.abc import Callable

from psycopg import Connection, Error
from psycopg.rows import dict_row

from ehf.domain.errors import DataReadError, TeamNotFound
from ehf.domain.team_detail import (
    LineupEntry,
    TeamCardData,
    TeamEdition,
    TeamHostVenue,
    TeamMatch,
    TeamProfile,
)
from ehf.infrastructure.kickoff import KICKOFF_AT_SQL
from ehf.infrastructure.played import (
    AWAY_NAME,
    EDITION_JOINS,
    HOME_NAME,
    SCORE_AWAY,
    SCORE_HOME,
    TEAM_JOINS,
)

PROFILE_SQL = """
SELECT
    cl.id,
    cl.ehf_id,
    latest.display_name AS name,
    cl.country_code,
    co.name AS country_name,
    COALESCE(latest.logo_url, cl.logo_url) AS logo_url,
    cl.website,
    cl.address,
    COALESCE(cl.profile_url, latest.profile_url) AS profile_url,
    (
        SELECT string_agg(DISTINCT c.gender, ',' ORDER BY c.gender)
        FROM ehf.club_edition ed
        JOIN ehf.competition_edition ce ON ce.id = ed.competition_edition_id
        JOIN ehf.competition c ON c.id = ce.competition_id
        WHERE ed.club_id = cl.id
    ) AS genders
FROM ehf.club cl
LEFT JOIN ehf.country co ON co.code = cl.country_code
LEFT JOIN LATERAL (
    SELECT ed.display_name, ed.logo_url, ed.profile_url
    FROM ehf.club_edition ed
    JOIN ehf.competition_edition ce ON ce.id = ed.competition_edition_id
    JOIN ehf.season s ON s.id = ce.season_id
    WHERE ed.club_id = cl.id
    ORDER BY s.year_start DESC, ed.id DESC
    LIMIT 1
) latest ON TRUE
WHERE cl.id = %s
"""

EDITION_SQL = """
SELECT
    s.id AS season_id,
    s.code AS season_code,
    s.year_start,
    c.id AS competition_id,
    c.name AS competition_name,
    ed.display_name AS name
FROM ehf.club_edition ed
JOIN ehf.competition_edition ce ON ce.id = ed.competition_edition_id
JOIN ehf.season s ON s.id = ce.season_id
JOIN ehf.competition c ON c.id = ce.competition_id
WHERE ed.club_id = %s
ORDER BY s.year_start DESC, c.name
"""

VENUE_SQL = """
SELECT
    v.id AS venue_id,
    v.name,
    v.city,
    COUNT(*)::int AS matches,
    AVG(m.spectators)::float AS average_spectators
FROM ehf.match m
JOIN ehf.venue v ON v.id = m.venue_id
WHERE m.home_club_id = %s
GROUP BY v.id, v.name, v.city
ORDER BY matches DESC, v.name
"""

IS_HOME = "m.home_club_id = %(club_id)s"

MATCH_SQL = f"""
SELECT
    m.id AS match_id,
    {KICKOFF_AT_SQL} AS kickoff_at,
    s.id AS season_id,
    s.code AS season_code,
    s.year_start,
    c.id AS competition_id,
    c.name AS competition_name,
    m.phase,
    m.group_code,
    CASE WHEN {IS_HOME} THEN 'home' ELSE 'away' END AS side,
    CASE WHEN {IS_HOME} THEN {HOME_NAME} ELSE {AWAY_NAME} END AS team_name,
    CASE WHEN {IS_HOME} THEN m.away_club_id ELSE m.home_club_id END AS opponent_id,
    CASE WHEN {IS_HOME} THEN {AWAY_NAME} ELSE {HOME_NAME} END AS opponent_name,
    {HOME_NAME} AS home_name,
    {AWAY_NAME} AS away_name,
    {SCORE_HOME} AS score_home,
    {SCORE_AWAY} AS score_away,
    COALESCE(m.full_time_home, {SCORE_HOME}) AS regular_home,
    COALESCE(m.full_time_away, {SCORE_AWAY}) AS regular_away,
    m.result_type,
    m.status,
    m.spectators
FROM ehf.match m
{EDITION_JOINS}
{TEAM_JOINS}
WHERE %(club_id)s IN (m.home_club_id, m.away_club_id)
ORDER BY {KICKOFF_AT_SQL} DESC NULLS LAST, m.id DESC
"""

ENTRY_SQL = f"""
SELECT
    l.match_id,
    t.side = CASE WHEN {IS_HOME} THEN 'home' ELSE 'away' END AS own,
    l.person_id,
    COALESCE(per.display_name, l.display_name, l.source_name, '—') AS name,
    l.shirt_number,
    COALESCE(pe.profile_position, per.profile_position) AS position,
    l.listed_as_goalkeeper AS is_goalkeeper,
    ps.goals,
    ps.shots,
    ps.yellow_cards,
    ps.two_min_suspensions,
    ps.red_cards,
    gk.saves,
    gk.shots_faced,
    EXTRACT(YEAR FROM per.birth_date)::int AS birth_year
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
LEFT JOIN ehf.match_player_stat ps ON ps.lineup_id = l.id
LEFT JOIN ehf.match_goalkeeper_stat gk ON gk.lineup_id = l.id
WHERE %(club_id)s IN (m.home_club_id, m.away_club_id)
ORDER BY l.match_id, l.id
"""


class PsycopgTeamDetailReader:
    def __init__(self, connect: Callable[[], Connection]) -> None:
        self._connect = connect

    def fetch(self, club_id: int) -> TeamCardData:
        params = {"club_id": club_id}
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(PROFILE_SQL, (club_id,))
                    profile = cursor.fetchone()
                    if profile is None:
                        raise TeamNotFound(club_id)
                    cursor.execute(EDITION_SQL, (club_id,))
                    editions = tuple(TeamEdition(**row) for row in cursor.fetchall())
                    cursor.execute(VENUE_SQL, (club_id,))
                    venues = tuple(TeamHostVenue(**row) for row in cursor.fetchall())
                    cursor.execute(MATCH_SQL, params)
                    matches = tuple(TeamMatch(**row) for row in cursor.fetchall())
                    cursor.execute(ENTRY_SQL, params)
                    entries = tuple(LineupEntry(**row) for row in cursor.fetchall())
        except TeamNotFound:
            raise
        except Error as exc:
            raise DataReadError(f"Could not read team {club_id}: {exc}") from exc
        return TeamCardData(
            profile=TeamProfile(**{**profile, "name": profile["name"] or f"Club {club_id}"}),
            editions=editions,
            venues=venues,
            matches=matches,
            entries=entries,
        )
