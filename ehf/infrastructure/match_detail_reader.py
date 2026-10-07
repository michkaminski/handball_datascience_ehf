from __future__ import annotations

from collections.abc import Callable

from psycopg import Connection, Error
from psycopg.rows import dict_row

from ehf.domain.errors import DataReadError, MatchNotFound
from ehf.domain.match_detail import (
    LineupPlayer,
    MatchDetail,
    MatchMetric,
    MatchOfficial,
    PeriodScore,
    TeamOfficial,
    TeamStats,
)
from ehf.domain.play_by_play import PlayAction, PlayParticipant

HEADER_SQL = """
SELECT
    m.id,
    m.ehf_match_id,
    m.kickoff_at,
    m.kickoff_display,
    s.code AS season_code,
    c.name AS competition_name,
    m.phase,
    m.group_code,
    v.name AS venue_name,
    v.city AS venue_city,
    COALESCE(home_ed.display_name, home_team.display_name) AS home_name,
    COALESCE(away_ed.display_name, away_team.display_name) AS away_name,
    home_club.id AS home_club_id,
    away_club.id AS away_club_id,
    home_club.country_code AS home_country,
    away_club.country_code AS away_country,
    COALESCE(m.score_home, home_team.goals) AS score_home,
    COALESCE(m.score_away, away_team.goals) AS score_away,
    m.half_time_home,
    m.half_time_away,
    m.result_type,
    m.status,
    m.spectators,
    m.source_url
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
LEFT JOIN ehf.club home_club ON home_club.id = COALESCE(m.home_club_id, home_team.club_id)
LEFT JOIN ehf.club away_club ON away_club.id = COALESCE(m.away_club_id, away_team.club_id)
LEFT JOIN ehf.venue v ON v.id = m.venue_id
WHERE m.id = %s
"""

PERIOD_SQL = """
SELECT p.period_code, sp.label, p.home, p.away, p.played
FROM ehf.match_period p
JOIN ehf.score_period sp ON sp.code = p.period_code
WHERE p.match_id = %s
ORDER BY sp.sort_order
"""

TEAM_SQL = """
SELECT side, display_name, goals, shots, penalty_goals, penalty_shots,
       yellow_cards, two_min_suspensions, red_cards
FROM ehf.match_team
WHERE match_id = %s
"""

LINEUP_SQL = """
SELECT
    t.side,
    l.person_id,
    l.shirt_number,
    COALESCE(l.display_name, l.source_name, per.display_name) AS name,
    COALESCE(pe.profile_position, per.profile_position) AS position,
    l.listed_as_goalkeeper,
    ps.goals,
    ps.shots,
    ps.yellow_cards,
    ps.two_min_suspensions,
    ps.red_cards,
    gk.saves,
    gk.shots_faced,
    gk.save_percentage
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
WHERE l.match_id = %s
ORDER BY t.side, l.listed_as_goalkeeper DESC, l.shirt_number NULLS LAST, l.id
"""

TEAM_OFFICIAL_SQL = """
SELECT t.side, o.official_code, COALESCE(o.display_name, o.source_name) AS name,
       o.yellow_cards, o.two_min_suspensions, o.red_cards
FROM ehf.match_team_official o
JOIN ehf.match_team t ON t.id = o.match_team_id
WHERE o.match_id = %s
ORDER BY t.side, o.official_code
"""

OFFICIAL_SQL = """
SELECT role, COALESCE(display_name, source_name) AS name, country_code
FROM ehf.match_official
WHERE match_id = %s
ORDER BY role, id
"""

PLAY_SQL = """
SELECT
    a.seq,
    a.action_code,
    a.period_code,
    a.clock_raw,
    a.result_code,
    a.shot_zone,
    a.action_add,
    a.score_home,
    a.score_away,
    p.side,
    p.role_code,
    p.shirt_number,
    p.first_name,
    p.last_name,
    p.person_id
FROM ehf.match_action a
LEFT JOIN ehf.match_action_actor p ON p.match_action_id = a.id
WHERE a.match_id = %s
ORDER BY a.seq, p.competitor_order NULLS FIRST, p.athlete_order NULLS FIRST, p.id
"""

METRIC_SQL = """
SELECT mm.metric_code, m.label, m.unit, mm.home_value, mm.away_value
FROM ehf.match_metric mm
JOIN ehf.metric m ON m.code = mm.metric_code
WHERE mm.match_id = %s
ORDER BY m.label
"""


class PsycopgMatchDetailReader:
    def __init__(self, connect: Callable[[], Connection]) -> None:
        self._connect = connect

    def fetch(self, match_id: int) -> MatchDetail:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(HEADER_SQL, (match_id,))
                    header = cursor.fetchone()
                    if header is None:
                        raise MatchNotFound(match_id)
                    cursor.execute(PERIOD_SQL, (match_id,))
                    periods = tuple(self._period(row) for row in cursor.fetchall())
                    cursor.execute(TEAM_SQL, (match_id,))
                    teams = {row["side"]: row for row in cursor.fetchall()}
                    cursor.execute(LINEUP_SQL, (match_id,))
                    lineups = cursor.fetchall()
                    cursor.execute(TEAM_OFFICIAL_SQL, (match_id,))
                    staff = cursor.fetchall()
                    cursor.execute(OFFICIAL_SQL, (match_id,))
                    officials = tuple(self._official(row) for row in cursor.fetchall())
                    cursor.execute(METRIC_SQL, (match_id,))
                    metrics = tuple(self._metric(row) for row in cursor.fetchall())
                    cursor.execute(PLAY_SQL, (match_id,))
                    play = self._play(cursor.fetchall())
        except MatchNotFound:
            raise
        except Error as exc:
            raise DataReadError(f"Could not read match {match_id}: {exc}") from exc

        return MatchDetail(
            id=header["id"],
            ehf_match_id=header["ehf_match_id"],
            kickoff_at=header["kickoff_at"],
            kickoff_display=header["kickoff_display"],
            season_code=header["season_code"],
            competition_name=header["competition_name"],
            phase=header["phase"],
            group_code=header["group_code"],
            venue_name=header["venue_name"],
            venue_city=header["venue_city"],
            home_name=header["home_name"],
            away_name=header["away_name"],
            home_club_id=header["home_club_id"],
            away_club_id=header["away_club_id"],
            home_country=header["home_country"],
            away_country=header["away_country"],
            score_home=header["score_home"],
            score_away=header["score_away"],
            half_time_home=header["half_time_home"],
            half_time_away=header["half_time_away"],
            result_type=header["result_type"],
            status=header["status"],
            spectators=header["spectators"],
            source_url=header["source_url"],
            home_stats=self._team_stats(teams.get("home"), header["home_name"]),
            away_stats=self._team_stats(teams.get("away"), header["away_name"]),
            periods=periods,
            home_lineup=tuple(self._player(row) for row in lineups if row["side"] == "home"),
            away_lineup=tuple(self._player(row) for row in lineups if row["side"] == "away"),
            home_officials=tuple(self._staff(row) for row in staff if row["side"] == "home"),
            away_officials=tuple(self._staff(row) for row in staff if row["side"] == "away"),
            officials=officials,
            metrics=metrics,
            play=play,
        )

    def _period(self, row: dict) -> PeriodScore:
        return PeriodScore(
            code=row["period_code"],
            label=row["label"],
            home=row["home"],
            away=row["away"],
            played=row["played"],
        )

    def _team_stats(self, row: dict | None, fallback_name: str | None) -> TeamStats | None:
        if row is None:
            return None
        return TeamStats(
            name=row["display_name"] or fallback_name or "—",
            goals=row["goals"],
            shots=row["shots"],
            penalty_goals=row["penalty_goals"],
            penalty_shots=row["penalty_shots"],
            yellow_cards=row["yellow_cards"],
            two_min_suspensions=row["two_min_suspensions"],
            red_cards=row["red_cards"],
        )

    def _player(self, row: dict) -> LineupPlayer:
        return LineupPlayer(
            person_id=row["person_id"],
            shirt_number=row["shirt_number"],
            name=row["name"] or "—",
            position=row["position"],
            is_goalkeeper=bool(row["listed_as_goalkeeper"]),
            goals=row["goals"],
            shots=row["shots"],
            yellow_cards=row["yellow_cards"],
            two_min_suspensions=row["two_min_suspensions"],
            red_cards=row["red_cards"],
            saves=row["saves"],
            shots_faced=row["shots_faced"],
            save_percentage=float(row["save_percentage"]) if row["save_percentage"] is not None else None,
        )

    def _staff(self, row: dict) -> TeamOfficial:
        return TeamOfficial(
            code=row["official_code"],
            name=row["name"] or "—",
            yellow_cards=row["yellow_cards"],
            two_min_suspensions=row["two_min_suspensions"],
            red_cards=row["red_cards"],
        )

    def _official(self, row: dict) -> MatchOfficial:
        return MatchOfficial(
            role=row["role"],
            name=row["name"] or "—",
            country_code=row["country_code"],
        )

    def _play(self, rows: list[dict]) -> tuple[PlayAction, ...]:
        grouped: list[PlayAction] = []
        current: dict | None = None
        people: list[PlayParticipant] = []
        for row in rows:
            if current is None or row["seq"] != current["seq"]:
                if current is not None:
                    grouped.append(self._play_action(current, people))
                current = row
                people = []
            if row["side"] is not None:
                people.append(
                    PlayParticipant(
                        side=row["side"],
                        role_code=row["role_code"],
                        shirt_number=row["shirt_number"],
                        first_name=row["first_name"],
                        last_name=row["last_name"],
                        person_id=row["person_id"],
                    )
                )
        if current is not None:
            grouped.append(self._play_action(current, people))
        return tuple(grouped)

    def _play_action(self, row: dict, people: list[PlayParticipant]) -> PlayAction:
        return PlayAction(
            seq=row["seq"],
            action_code=row["action_code"],
            period_code=row["period_code"],
            clock_raw=row["clock_raw"],
            result_code=row["result_code"],
            shot_zone=row["shot_zone"],
            action_add=row["action_add"],
            score_home=row["score_home"],
            score_away=row["score_away"],
            participants=tuple(people),
        )

    def _metric(self, row: dict) -> MatchMetric:
        return MatchMetric(
            code=row["metric_code"],
            label=row["label"],
            unit=row["unit"],
            home_value=float(row["home_value"]) if row["home_value"] is not None else None,
            away_value=float(row["away_value"]) if row["away_value"] is not None else None,
        )
