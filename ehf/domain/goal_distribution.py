from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from ehf.domain.gender import GENDERS
from ehf.domain.matches import Choice


def format_int(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def format_decimal(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.1f}"


def format_share(share: float) -> str:
    return f"{share * 100:.1f}%"


@dataclass(frozen=True)
class GoalDistributionFilters:
    season_id: int | None = None
    competition_id: int | None = None
    gender: str | None = None

    def __post_init__(self) -> None:
        if self.gender is not None and self.gender not in GENDERS:
            raise ValueError("gender must be men or women")


@dataclass(frozen=True)
class GoalFilterChoices:
    seasons: tuple[Choice, ...]
    competitions: tuple[Choice, ...]


@dataclass(frozen=True)
class GoalScoreline:
    home: int
    away: int
    matches: int

    def __post_init__(self) -> None:
        if self.matches < 1:
            raise ValueError("match count must be positive")
        if self.home < 0 or self.away < 0:
            raise ValueError("goals cannot be negative")


@dataclass(frozen=True)
class GoalBin:
    goals: int
    matches: int
    share: float
    cumulative: float
    width: float
    is_mode: bool

    @property
    def matches_label(self) -> str:
        return format_int(self.matches)

    @property
    def share_label(self) -> str:
        return format_share(self.share)

    @property
    def cumulative_label(self) -> str:
        return format_share(self.cumulative)


@dataclass(frozen=True)
class GoalSeries:
    match_count: int
    mean: float | None
    median: float | None
    modes: tuple[int, ...]
    minimum: int | None
    maximum: int | None
    bins: tuple[GoalBin, ...]

    @property
    def match_count_label(self) -> str:
        return format_int(self.match_count)

    @property
    def mean_label(self) -> str:
        return format_decimal(self.mean)

    @property
    def median_label(self) -> str:
        return format_decimal(self.median)

    @property
    def modes_label(self) -> str:
        if not self.modes:
            return "—"
        return ", ".join(str(value) for value in self.modes)

    @property
    def range_label(self) -> str:
        if self.minimum is None or self.maximum is None:
            return "—"
        return f"{self.minimum}–{self.maximum}"


@dataclass(frozen=True)
class GoalDistributionReport:
    total: GoalSeries
    home: GoalSeries
    away: GoalSeries


class SeriesKind(StrEnum):
    TOTAL = "total"
    HOME = "home"
    AWAY = "away"


@dataclass(frozen=True)
class GoalMatch:
    match_id: int
    kickoff: datetime | None
    season: str
    competition: str
    home: str
    away: str
    home_goals: int
    away_goals: int

    @property
    def kickoff_label(self) -> str:
        if self.kickoff is None:
            return "—"
        if self.kickoff.hour or self.kickoff.minute:
            return self.kickoff.strftime("%Y-%m-%d %H:%M")
        return self.kickoff.strftime("%Y-%m-%d")

    @property
    def score_label(self) -> str:
        return f"{self.home_goals}:{self.away_goals}"


def series_kind(text: str | None) -> SeriesKind:
    try:
        return SeriesKind(text or "")
    except ValueError as exc:
        raise ValueError("unsupported series") from exc


def require_goals(goals: int) -> int:
    if goals < 0:
        raise ValueError("goals cannot be negative")
    return goals


def build_series(counts: Mapping[int, int]) -> GoalSeries:
    clean = {int(goals): int(matches) for goals, matches in counts.items() if matches > 0}
    total = sum(clean.values())
    if total == 0:
        return GoalSeries(0, None, None, (), None, None, ())
    peak = max(clean.values())
    modes = (
        tuple(sorted(goals for goals, matches in clean.items() if matches == peak))
        if peak > 1
        else ()
    )
    mode_set = set(modes)
    minimum = min(clean)
    maximum = max(clean)
    bins: list[GoalBin] = []
    running = 0
    for goals in range(minimum, maximum + 1):
        matches = clean.get(goals, 0)
        running += matches
        bins.append(
            GoalBin(
                goals=goals,
                matches=matches,
                share=matches / total,
                cumulative=running / total,
                width=100 * matches / peak,
                is_mode=goals in mode_set,
            )
        )
    return GoalSeries(
        match_count=total,
        mean=sum(goals * matches for goals, matches in clean.items()) / total,
        median=_median(clean, total),
        modes=modes,
        minimum=minimum,
        maximum=maximum,
        bins=tuple(bins),
    )


def series_from_scorelines(
    scorelines: Sequence[GoalScoreline],
) -> tuple[GoalSeries, GoalSeries, GoalSeries]:
    totals: dict[int, int] = {}
    home: dict[int, int] = {}
    away: dict[int, int] = {}
    for line in scorelines:
        _add(totals, line.home + line.away, line.matches)
        _add(home, line.home, line.matches)
        _add(away, line.away, line.matches)
    return build_series(totals), build_series(home), build_series(away)


def _add(counts: dict[int, int], goals: int, matches: int) -> None:
    counts[goals] = counts.get(goals, 0) + matches


def _median(counts: Mapping[int, int], total: int) -> float:
    if total % 2 == 1:
        wanted = [total // 2 + 1]
    else:
        wanted = [total // 2, total // 2 + 1]
    found: list[int] = []
    seen = 0
    for goals in sorted(counts):
        seen += counts[goals]
        while wanted and seen >= wanted[0]:
            found.append(goals)
            wanted.pop(0)
        if not wanted:
            break
    return sum(found) / len(found)
