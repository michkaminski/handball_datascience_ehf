from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from ehf.domain.matches import format_score


@dataclass(frozen=True)
class PeriodScore:
    code: str
    label: str
    home: int
    away: int
    played: bool


@dataclass(frozen=True)
class TeamStats:
    name: str
    goals: int | None
    shots: int | None
    penalty_goals: int | None
    penalty_shots: int | None
    yellow_cards: int | None
    two_min_suspensions: int | None
    red_cards: int | None


@dataclass(frozen=True)
class LineupPlayer:
    shirt_number: str | None
    name: str
    position: str | None
    is_goalkeeper: bool
    goals: int | None
    shots: int | None
    yellow_cards: int | None
    two_min_suspensions: int | None
    red_cards: int | None
    saves: int | None
    shots_faced: int | None
    save_percentage: float | None
    top_scorer: bool = False

    @property
    def position_label(self) -> str | None:
        text = (self.position or "").strip()
        if text:
            return text
        if self.is_goalkeeper:
            return "Goalkeeper"
        return None

    @property
    def save_percentage_text(self) -> str | None:
        if self.save_percentage is None:
            return None
        value = self.save_percentage
        if value == int(value):
            return f"{int(value)}%"
        return f"{value:.1f}%"


@dataclass(frozen=True)
class TeamOfficial:
    code: str
    name: str
    yellow_cards: int | None
    two_min_suspensions: int | None
    red_cards: int | None


@dataclass(frozen=True)
class MatchOfficial:
    role: str
    name: str
    country_code: str | None


@dataclass(frozen=True)
class MatchMetric:
    code: str
    label: str
    unit: str
    home_value: float | None
    away_value: float | None


@dataclass(frozen=True)
class MatchDetail:
    id: int
    ehf_match_id: str
    kickoff_at: datetime | None
    kickoff_display: str | None
    season_code: str | None
    competition_name: str | None
    phase: str | None
    group_code: str | None
    venue_name: str | None
    venue_city: str | None
    home_name: str | None
    away_name: str | None
    score_home: int | None
    score_away: int | None
    half_time_home: int | None
    half_time_away: int | None
    result_type: str | None
    status: str
    spectators: int | None
    source_url: str | None
    home_stats: TeamStats | None
    away_stats: TeamStats | None
    periods: tuple[PeriodScore, ...]
    home_lineup: tuple[LineupPlayer, ...]
    away_lineup: tuple[LineupPlayer, ...]
    home_officials: tuple[TeamOfficial, ...]
    away_officials: tuple[TeamOfficial, ...]
    officials: tuple[MatchOfficial, ...]
    metrics: tuple[MatchMetric, ...]

    @property
    def score_text(self) -> str:
        return format_score(self.score_home, self.score_away, self.result_type)

    @property
    def half_time_text(self) -> str:
        return format_score(self.half_time_home, self.half_time_away)

    def with_top_scorers(self) -> MatchDetail:
        return replace(
            self,
            home_lineup=mark_top_scorers(self.home_lineup),
            away_lineup=mark_top_scorers(self.away_lineup),
        )


def mark_top_scorers(players: tuple[LineupPlayer, ...]) -> tuple[LineupPlayer, ...]:
    scored = [player.goals for player in players if player.goals is not None]
    if not scored:
        return players
    best = max(scored)
    if best <= 0:
        return players
    return tuple(replace(player, top_scorer=player.goals == best) for player in players)
