from __future__ import annotations

from collections.abc import Callable

from psycopg import Connection, Error
from psycopg.rows import dict_row

from ehf.domain.errors import DataReadError, PlayerNotFound
from ehf.domain.matches import Choice
from ehf.domain.players import (
    PlayerMatchFilterOptions,
    PlayerMatchFilters,
    PlayerMatchItem,
    PlayerMatchPage,
    PlayerProfile,
    PlayerSeasonRow,
)
from ehf.infrastructure.kickoff import KICKOFF_AT_SQL
from ehf.infrastructure.ordering import order_sql
from ehf.infrastructure.player_list_reader import APPEARANCE_FROM, TEAM_NAME

PROFILE_SQL = """
SELECT
    p.id,
    p.display_name,
    p.first_name,
    p.last_name,
    p.birth_date,
    p.birth_place,
    p.height_cm,
    p.weight_kg,
    p.profile_position AS position,
    p.photo_url,
    p.profile_url,
    p.ehf_id,
    COALESCE(
        array_agg(n.nationality ORDER BY n.nationality) FILTER (WHERE n.nationality IS NOT NULL),
        ARRAY[]::text[]
    ) AS nationalities
FROM ehf.person p
LEFT JOIN ehf.person_nationality n ON n.person_id = p.id
WHERE p.id = %s
GROUP BY p.id
"""

SEASON_SQL = f"""
SELECT
    s.code AS season_code,
    s.year_start,
    c.name AS competition_name,
    {TEAM_NAME} AS team_name,
    COUNT(DISTINCT l.match_id) AS matches,
    SUM(ps.goals) AS goals,
    SUM(ps.shots) AS shots,
    SUM(ps.yellow_cards) AS yellow_cards,
    SUM(ps.two_min_suspensions) AS two_min_suspensions,
    SUM(ps.red_cards) AS red_cards,
    SUM(gk.saves) AS saves,
    SUM(gk.shots_faced) AS shots_faced
{APPEARANCE_FROM}
LEFT JOIN ehf.match_player_stat ps ON ps.lineup_id = l.id
LEFT JOIN ehf.match_goalkeeper_stat gk ON gk.lineup_id = l.id
WHERE l.person_id = %s
GROUP BY s.code, s.year_start, c.name, {TEAM_NAME}
ORDER BY s.year_start DESC, c.name, {TEAM_NAME}
"""

MATCH_SELECT = f"""
SELECT
    m.id AS match_id,
    {KICKOFF_AT_SQL} AS kickoff_at,
    s.code AS season_code,
    c.name AS competition_name,
    COALESCE(home_ed.display_name, home_team.display_name) AS home_name,
    COALESCE(away_ed.display_name, away_team.display_name) AS away_name,
    COALESCE(m.score_home, home_team.goals) AS score_home,
    COALESCE(m.score_away, away_team.goals) AS score_away,
    m.result_type,
    {TEAM_NAME} AS team_name,
    t.side,
    ps.goals,
    ps.shots,
    ps.two_min_suspensions,
    gk.saves,
    gk.shots_faced
{APPEARANCE_FROM}
LEFT JOIN ehf.match_team home_team
    ON home_team.match_id = m.id AND home_team.side = 'home'
LEFT JOIN ehf.match_team away_team
    ON away_team.match_id = m.id AND away_team.side = 'away'
LEFT JOIN ehf.club_edition home_ed
    ON home_ed.club_id = m.home_club_id
   AND home_ed.competition_edition_id = m.competition_edition_id
LEFT JOIN ehf.club_edition away_ed
    ON away_ed.club_id = m.away_club_id
   AND away_ed.competition_edition_id = m.competition_edition_id
LEFT JOIN ehf.match_player_stat ps ON ps.lineup_id = l.id
LEFT JOIN ehf.match_goalkeeper_stat gk ON gk.lineup_id = l.id
WHERE l.person_id = %s
"""

PLAYER_MATCH_ORDER = {
    "date": (KICKOFF_AT_SQL,),
    "season": ("s.code",),
    "competition": ("c.name",),
    "team": (TEAM_NAME,),
    "opponent": (
        "CASE WHEN t.side = 'home' THEN COALESCE(away_ed.display_name, away_team.display_name) "
        "ELSE COALESCE(home_ed.display_name, home_team.display_name) END",
    ),
    "score": (
        "COALESCE(m.score_home, home_team.goals)",
        "COALESCE(m.score_away, away_team.goals)",
    ),
    "goals": ("ps.goals",),
    "shots": ("ps.shots",),
    "shot_pct": ("CASE WHEN ps.shots > 0 THEN ps.goals::numeric / ps.shots END",),
    "two_min": ("ps.two_min_suspensions",),
    "saves": ("gk.saves",),
    "faced": ("gk.shots_faced",),
    "save_pct": ("CASE WHEN gk.shots_faced > 0 THEN gk.saves::numeric / gk.shots_faced END",),
}


class PsycopgPlayerDetailReader:
    def __init__(self, connect: Callable[[], Connection]) -> None:
        self._connect = connect

    def fetch_profile(self, player_id: int) -> PlayerProfile:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(PROFILE_SQL, (player_id,))
                    row = cursor.fetchone()
        except Error as exc:
            raise DataReadError(f"Could not read player {player_id}: {exc}") from exc
        if row is None:
            raise PlayerNotFound(player_id)
        return PlayerProfile(
            id=row["id"],
            display_name=row["display_name"] or "—",
            first_name=row["first_name"],
            last_name=row["last_name"],
            birth_date=row["birth_date"],
            birth_place=row["birth_place"],
            height_cm=row["height_cm"],
            weight_kg=float(row["weight_kg"]) if row["weight_kg"] is not None else None,
            position=row["position"],
            photo_url=row["photo_url"],
            profile_url=row["profile_url"],
            ehf_id=row["ehf_id"],
            nationalities=tuple(row["nationalities"] or ()),
        )

    def fetch_seasons(self, player_id: int) -> tuple[PlayerSeasonRow, ...]:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(SEASON_SQL, (player_id,))
                    rows = cursor.fetchall()
        except Error as exc:
            raise DataReadError(f"Could not read player seasons {player_id}: {exc}") from exc
        return tuple(self._season(row) for row in rows)

    def fetch_matches(self, player_id: int, filters: PlayerMatchFilters) -> PlayerMatchPage:
        extra_sql, extra_params = self._match_where(filters)
        where_sql = MATCH_SELECT + extra_sql
        count_sql = f"SELECT COUNT(*) FROM ({where_sql}) AS listed"
        page_sql = (
            f"{where_sql} {order_sql(filters.sort, PLAYER_MATCH_ORDER, 'm.id')} LIMIT %s OFFSET %s"
        )
        params = (player_id, *extra_params)
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(count_sql, params)
                    total = int(cursor.fetchone()[0])
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        page_sql,
                        (
                            *params,
                            filters.page_size,
                            (filters.page - 1) * filters.page_size,
                        ),
                    )
                    rows = cursor.fetchall()
        except Error as exc:
            raise DataReadError(f"Could not read player matches {player_id}: {exc}") from exc
        return PlayerMatchPage(
            items=tuple(self._match(row) for row in rows),
            total=total,
            filters=filters,
        )

    def fetch_match_options(self, player_id: int) -> PlayerMatchFilterOptions:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    seasons = self._choices(
                        cursor,
                        f"SELECT DISTINCT s.id::text AS value, s.code AS label "
                        f"{APPEARANCE_FROM} WHERE l.person_id = %s ORDER BY s.code DESC",
                        (player_id,),
                    )
                    competitions = self._choices(
                        cursor,
                        f"SELECT DISTINCT c.id::text AS value, c.name AS label "
                        f"{APPEARANCE_FROM} WHERE l.person_id = %s ORDER BY c.name",
                        (player_id,),
                    )
                    clubs = self._choices(
                        cursor,
                        f"SELECT t.club_id::text AS value, MIN({TEAM_NAME}) AS label "
                        f"{APPEARANCE_FROM} WHERE l.person_id = %s AND t.club_id IS NOT NULL "
                        f"GROUP BY t.club_id ORDER BY MIN({TEAM_NAME})",
                        (player_id,),
                    )
        except Error as exc:
            raise DataReadError(f"Could not read player match filters {player_id}: {exc}") from exc
        return PlayerMatchFilterOptions(seasons=seasons, competitions=competitions, clubs=clubs)

    def _match_where(self, filters: PlayerMatchFilters) -> tuple[str, list[object]]:
        clauses: list[str] = []
        params: list[object] = []
        if filters.season_id is not None:
            clauses.append("s.id = %s")
            params.append(filters.season_id)
        if filters.competition_id is not None:
            clauses.append("c.id = %s")
            params.append(filters.competition_id)
        if filters.club_id is not None:
            clauses.append("t.club_id = %s")
            params.append(filters.club_id)
        if filters.match_date is not None:
            clauses.append(f"{KICKOFF_AT_SQL}::date = %s")
            params.append(filters.match_date)
        if not clauses:
            return "", params
        return " AND " + " AND ".join(clauses), params

    def _choices(self, cursor, sql: str, params: tuple[object, ...] = ()) -> tuple[Choice, ...]:
        cursor.execute(sql, params)
        return tuple(Choice(value=row["value"], label=row["label"]) for row in cursor.fetchall())

    def _season(self, row: dict) -> PlayerSeasonRow:
        return PlayerSeasonRow(
            season_code=row["season_code"],
            competition_name=row["competition_name"],
            team_name=row["team_name"],
            matches=int(row["matches"] or 0),
            goals=row["goals"],
            shots=row["shots"],
            yellow_cards=row["yellow_cards"],
            two_min_suspensions=row["two_min_suspensions"],
            red_cards=row["red_cards"],
            saves=row["saves"],
            shots_faced=row["shots_faced"],
        )

    def _match(self, row: dict) -> PlayerMatchItem:
        opponent = row["away_name"] if row["side"] == "home" else row["home_name"]
        return PlayerMatchItem(
            match_id=row["match_id"],
            kickoff_at=row["kickoff_at"],
            season_code=row["season_code"],
            competition_name=row["competition_name"],
            home_name=row["home_name"],
            away_name=row["away_name"],
            score_home=row["score_home"],
            score_away=row["score_away"],
            result_type=row["result_type"],
            team_name=row["team_name"],
            opponent_name=opponent,
            goals=row["goals"],
            shots=row["shots"],
            two_min_suspensions=row["two_min_suspensions"],
            saves=row["saves"],
            shots_faced=row["shots_faced"],
            side=row["side"],
        )
