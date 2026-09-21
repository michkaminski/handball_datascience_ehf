from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from ehf.domain.match_detail import format_percentage, ratio_percentage
from ehf.domain.matches import Choice, format_score
from ehf.domain.sorting import DEFAULT_PLAYER_MATCH_SORT, DEFAULT_PLAYER_SORT, Sort


@dataclass(frozen=True)
class PlayerFilters:
    season_id: int | None = None
    competition_id: int | None = None
    club_id: int | None = None
    position: str | None = None
    birth_year: int | None = None
    query: str | None = None
    sort: Sort = DEFAULT_PLAYER_SORT
    page: int = 1
    page_size: int = 50

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page must be >= 1")
        if not 1 <= self.page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")


@dataclass(frozen=True)
class PlayerFilterOptions:
    seasons: tuple[Choice, ...]
    competitions: tuple[Choice, ...]
    clubs: tuple[Choice, ...]
    positions: tuple[Choice, ...]
    birth_years: tuple[Choice, ...]


@dataclass(frozen=True)
class PlayerListItem:
    id: int
    first_name: str | None
    last_name: str | None
    display_name: str
    position: str | None
    teams: str | None
    birth_year: int | None
    height_cm: int | None
    weight_kg: float | None


@dataclass(frozen=True)
class PlayerListPage:
    items: tuple[PlayerListItem, ...]
    total: int
    filters: PlayerFilters

    @property
    def has_previous(self) -> bool:
        return self.filters.page > 1

    @property
    def has_next(self) -> bool:
        return self.filters.page * self.filters.page_size < self.total


@dataclass(frozen=True)
class PlayerMatchFilters:
    season_id: int | None = None
    competition_id: int | None = None
    club_id: int | None = None
    match_date: date | None = None
    sort: Sort = DEFAULT_PLAYER_MATCH_SORT
    page: int = 1
    page_size: int = 50

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page must be >= 1")
        if not 1 <= self.page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")


@dataclass(frozen=True)
class PlayerMatchFilterOptions:
    seasons: tuple[Choice, ...]
    competitions: tuple[Choice, ...]
    clubs: tuple[Choice, ...]


@dataclass(frozen=True)
class PlayerProfile:
    id: int
    display_name: str
    first_name: str | None
    last_name: str | None
    birth_date: date | None
    birth_place: str | None
    height_cm: int | None
    weight_kg: float | None
    position: str | None
    photo_url: str | None
    profile_url: str | None
    ehf_id: str | None
    nationalities: tuple[str, ...]

    @property
    def birth_year(self) -> int | None:
        return None if self.birth_date is None else self.birth_date.year

    @property
    def nationality_text(self) -> str:
        return ", ".join(self.nationalities) if self.nationalities else "—"


@dataclass(frozen=True)
class PlayerSeasonRow:
    season_code: str | None
    competition_name: str | None
    team_name: str | None
    matches: int
    goals: int | None
    shots: int | None
    yellow_cards: int | None
    two_min_suspensions: int | None
    red_cards: int | None
    saves: int | None
    shots_faced: int | None

    @property
    def shot_percentage_text(self) -> str | None:
        return format_percentage(ratio_percentage(self.goals, self.shots))

    @property
    def save_percentage_text(self) -> str | None:
        return format_percentage(ratio_percentage(self.saves, self.shots_faced))


@dataclass(frozen=True)
class PlayerMatchItem:
    match_id: int
    kickoff_at: datetime | None
    season_code: str | None
    competition_name: str | None
    home_name: str | None
    away_name: str | None
    score_home: int | None
    score_away: int | None
    result_type: str | None
    team_name: str | None
    opponent_name: str | None
    goals: int | None
    shots: int | None
    two_min_suspensions: int | None
    saves: int | None
    shots_faced: int | None

    @property
    def score_text(self) -> str:
        return format_score(self.score_home, self.score_away, self.result_type)

    @property
    def shot_percentage_text(self) -> str | None:
        return format_percentage(ratio_percentage(self.goals, self.shots))

    @property
    def save_percentage_text(self) -> str | None:
        return format_percentage(ratio_percentage(self.saves, self.shots_faced))


@dataclass(frozen=True)
class PlayerMatchPage:
    items: tuple[PlayerMatchItem, ...]
    total: int
    filters: PlayerMatchFilters

    @property
    def has_previous(self) -> bool:
        return self.filters.page > 1

    @property
    def has_next(self) -> bool:
        return self.filters.page * self.filters.page_size < self.total


@dataclass(frozen=True)
class PlayerCard:
    profile: PlayerProfile
    seasons: tuple[PlayerSeasonRow, ...]
    matches: PlayerMatchPage
    match_options: PlayerMatchFilterOptions
