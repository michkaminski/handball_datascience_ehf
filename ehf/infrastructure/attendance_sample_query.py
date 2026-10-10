from __future__ import annotations

from ehf.domain.attendance_science import MatchSample
from ehf.infrastructure.kickoff import KICKOFF_AT_SQL
from ehf.infrastructure.played import (
    AWAY_NAME,
    EDITION_JOINS,
    HOME_NAME,
    SCORE_AWAY,
    SCORE_HOME,
    TEAM_JOINS,
)


def sample_sql(
    where: str, params: list[object], known: str, limit: int
) -> tuple[str, list[object]]:
    sql = f"""
SELECT
    m.id,
    {KICKOFF_AT_SQL} AS kickoff_at,
    m.home_club_id,
    m.away_club_id,
    COALESCE(NULLIF(btrim({HOME_NAME}), ''), '—') AS home_name,
    COALESCE(NULLIF(btrim({AWAY_NAME}), ''), '—') AS away_name,
    {SCORE_HOME} AS score_home,
    {SCORE_AWAY} AS score_away,
    m.spectators
FROM ehf.match m
{EDITION_JOINS}
{TEAM_JOINS}
WHERE {where} AND {known}
ORDER BY {KICKOFF_AT_SQL} DESC NULLS LAST, m.id DESC
LIMIT %s
"""
    return sql, [*params, limit]


def sample_from_row(row: dict) -> MatchSample:
    return MatchSample(
        match_id=int(row["id"]),
        kickoff=row["kickoff_at"],
        spectators=int(row["spectators"]),
        home_club_id=row["home_club_id"],
        away_club_id=row["away_club_id"],
        home=str(row["home_name"]),
        away=str(row["away_name"]),
        home_goals=row["score_home"],
        away_goals=row["score_away"],
    )
