from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from ehf.domain.sorting import DEFAULT_MATCH_SORT, Sort


def format_score(home: int | None, away: int | None, result_type: str | None = None) -> str:
    if home is None or away is None:
        return "—"
    text = f"{home}:{away}"
    if result_type and result_type != "normal":
        return f"{text} ({result_type})"
    return text


def format_stage(phase: str | None, group_code: str | None) -> str:
    if phase and group_code:
        return f"{phase} ({group_code})"
    return phase or group_code or "—"


@dataclass(frozen=True)
class MatchFilters:
    season_id: int | None = None
    competition_id: int | None = None
    phase: str | None = None
    group_code: str | None = None
    venue_id: int | None = None
    club_query: str | None = None
    match_date: date | None = None
    sort: Sort = DEFAULT_MATCH_SORT
    page: int = 1
    page_size: int = 50

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page must be >= 1")
        if not 1 <= self.page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")


@dataclass(frozen=True)
class Choice:
    value: str
    label: str


@dataclass(frozen=True)
class MatchFilterOptions:
    seasons: tuple[Choice, ...]
    competitions: tuple[Choice, ...]
    phases: tuple[Choice, ...]
    groups: tuple[Choice, ...]
    venues: tuple[Choice, ...]


@dataclass(frozen=True)
class MatchListItem:
    id: int
    kickoff_at: datetime | None
    season_code: str | None
    competition_name: str | None
    home_name: str | None
    away_name: str | None
    score_home: int | None
    score_away: int | None
    result_type: str | None
    status: str
    venue_name: str | None
    spectators: int | None
    phase: str | None
    group_code: str | None
    home_club_id: int | None = None
    away_club_id: int | None = None

    @property
    def score_text(self) -> str:
        return format_score(self.score_home, self.score_away, self.result_type)

    @property
    def stage_text(self) -> str:
        return format_stage(self.phase, self.group_code)


@dataclass(frozen=True)
class MatchListPage:
    items: tuple[MatchListItem, ...]
    total: int
    filters: MatchFilters

    @property
    def has_previous(self) -> bool:
        return self.filters.page > 1

    @property
    def has_next(self) -> bool:
        return self.filters.page * self.filters.page_size < self.total
