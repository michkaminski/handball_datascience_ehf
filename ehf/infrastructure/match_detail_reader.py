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
    l.shirt_number,
    COALESCE(l.display_name, l.source_name, per.display_name) AS name,
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
LEFT JOIN ehf.person per ON per.id = l.person_id
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
            shirt_number=row["shirt_number"],
            name=row["name"] or "—",
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

    def _metric(self, row: dict) -> MatchMetric:
        return MatchMetric(
            code=row["metric_code"],
            label=row["label"],
            unit=row["unit"],
            home_value=float(row["home_value"]) if row["home_value"] is not None else None,
            away_value=float(row["away_value"]) if row["away_value"] is not None else None,
        )
