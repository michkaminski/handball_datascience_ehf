from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from ehf.domain.matches import format_score
from ehf.domain.play_by_play import PlayAction
from ehf.domain.play_timeline import PlayTimeline, present_timeline


def format_percentage(value: float | None) -> str | None:
    if value is None:
        return None
    if value == int(value):
        return f"{int(value)}%"
    return f"{value:.1f}%"


def ratio_percentage(made: int | None, attempts: int | None) -> float | None:
    if made is None or attempts is None or attempts <= 0:
        return None
    return made * 100 / attempts


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
    person_id: int | None = None

    @property
    def position_label(self) -> str | None:
        text = (self.position or "").strip()
        if text:
            return text
        if self.is_goalkeeper:
            return "Goalkeeper"
        return None

    @property
    def shot_percentage_text(self) -> str | None:
        return format_percentage(ratio_percentage(self.goals, self.shots))

    @property
    def save_percentage_text(self) -> str | None:
        return format_percentage(self.save_percentage)


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
class EfficiencyLine:
    label: str
    made: int | None
    attempts: int | None

    @property
    def percentage(self) -> float | None:
        return ratio_percentage(self.made, self.attempts)

    @property
    def ratio_text(self) -> str:
        if self.made is None or self.attempts is None:
            return "—"
        return f"{self.made}/{self.attempts}"

    @property
    def percentage_text(self) -> str:
        return format_percentage(self.percentage) or ""

    @property
    def text(self) -> str:
        pct = self.percentage_text
        if self.made is None or self.attempts is None:
            return "—"
        if pct:
            return f"{self.ratio_text} ({pct})"
        return self.ratio_text


@dataclass(frozen=True)
class SummaryRow:
    label: str
    value: str
    extra: str = ""


@dataclass(frozen=True)
class TeamEfficiency:
    saves: EfficiencyLine
    shots: EfficiencyLine
    penalties: EfficiencyLine
    short_handed_minutes: int | None

    @property
    def rows(self) -> tuple[SummaryRow, ...]:
        minutes = "—" if self.short_handed_minutes is None else f"{self.short_handed_minutes} min"
        return (
            SummaryRow(self.saves.label, self.saves.ratio_text, self.saves.percentage_text),
            SummaryRow(self.shots.label, self.shots.ratio_text, self.shots.percentage_text),
            SummaryRow(self.penalties.label, self.penalties.ratio_text, self.penalties.percentage_text),
            SummaryRow("Short-handed", minutes),
        )


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
    home_country: str | None
    away_country: str | None
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
    home_club_id: int | None = None
    away_club_id: int | None = None
    play: tuple[PlayAction, ...] = ()

    @property
    def play_view(self) -> PlayTimeline:
        return present_timeline(self.play, self.home_title, self.away_title)

    @property
    def home_title(self) -> str:
        return self.home_name or "—"

    @property
    def away_title(self) -> str:
        return self.away_name or "—"

    @property
    def score_text(self) -> str:
        return format_score(self.score_home, self.score_away, self.result_type)

    @property
    def half_time_text(self) -> str:
        return format_score(self.half_time_home, self.half_time_away)

    @property
    def home_efficiency(self) -> TeamEfficiency:
        return team_efficiency(self.home_stats, self.home_lineup, self.home_officials)

    @property
    def away_efficiency(self) -> TeamEfficiency:
        return team_efficiency(self.away_stats, self.away_lineup, self.away_officials)

    def with_top_scorers(self) -> MatchDetail:
        return replace(
            self,
            home_lineup=mark_top_scorers(self.home_lineup),
            away_lineup=mark_top_scorers(self.away_lineup),
        )


def short_handed_minutes(
    stats: TeamStats | None,
    lineup: tuple[LineupPlayer, ...],
    officials: tuple[TeamOfficial, ...] = (),
) -> int | None:
    if stats is not None and stats.two_min_suspensions is not None:
        return stats.two_min_suspensions * 2
    counted = [player.two_min_suspensions for player in lineup if player.two_min_suspensions is not None]
    counted.extend(person.two_min_suspensions for person in officials if person.two_min_suspensions is not None)
    if not counted:
        return None
    return sum(counted) * 2


def team_efficiency(
    stats: TeamStats | None,
    lineup: tuple[LineupPlayer, ...],
    officials: tuple[TeamOfficial, ...] = (),
) -> TeamEfficiency:
    has_saves = any(player.saves is not None or player.shots_faced is not None for player in lineup)
    saves = sum(player.saves or 0 for player in lineup if player.saves is not None)
    faced = sum(player.shots_faced or 0 for player in lineup if player.shots_faced is not None)
    return TeamEfficiency(
        saves=EfficiencyLine("GK saves", saves if has_saves else None, faced if has_saves else None),
        shots=EfficiencyLine(
            "Shooting",
            None if stats is None else stats.goals,
            None if stats is None else stats.shots,
        ),
        penalties=EfficiencyLine(
            "7m",
            None if stats is None else stats.penalty_goals,
            None if stats is None else stats.penalty_shots,
        ),
        short_handed_minutes=short_handed_minutes(stats, lineup, officials),
    )


def mark_top_scorers(players: tuple[LineupPlayer, ...]) -> tuple[LineupPlayer, ...]:
    scored = [player.goals for player in players if player.goals is not None]
    if not scored:
        return players
    best = max(scored)
    if best <= 0:
        return players
    return tuple(replace(player, top_scorer=player.goals == best) for player in players)
