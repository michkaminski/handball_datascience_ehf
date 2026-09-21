from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from ehf.domain.counts import CountSeries, Heatmap, MatchRecord
from ehf.domain.match_detail import format_percentage
from ehf.domain.matches import Choice, format_score
from ehf.domain.sorting import DEFAULT_VENUE_MATCH_SORT, DEFAULT_VENUE_PLAYER_SORT, DEFAULT_VENUE_SORT, Sort


@dataclass(frozen=True)
class VenueFilters:
    query: str | None = None
    city: str | None = None
    sort: Sort = DEFAULT_VENUE_SORT
    page: int = 1
    page_size: int = 50

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page must be >= 1")
        if not 1 <= self.page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")


@dataclass(frozen=True)
class VenueFilterOptions:
    cities: tuple[Choice, ...]


@dataclass(frozen=True)
class VenueListItem:
    id: int
    name: str
    city: str | None
    country_code: str | None
    country_name: str | None
    matches: int


@dataclass(frozen=True)
class VenueListPage:
    items: tuple[VenueListItem, ...]
    total: int
    filters: VenueFilters

    @property
    def has_previous(self) -> bool:
        return self.filters.page > 1

    @property
    def has_next(self) -> bool:
        return self.filters.page * self.filters.page_size < self.total


@dataclass(frozen=True)
class VenueMatchFilters:
    season_id: int | None = None
    competition_id: int | None = None
    club_id: int | None = None
    sort: Sort = DEFAULT_VENUE_MATCH_SORT
    page: int = 1
    page_size: int = 50

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page must be >= 1")
        if not 1 <= self.page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")


@dataclass(frozen=True)
class VenueMatchFilterOptions:
    seasons: tuple[Choice, ...]
    competitions: tuple[Choice, ...]
    clubs: tuple[Choice, ...]


@dataclass(frozen=True)
class VenueMatchItem:
    match_id: int
    kickoff_at: datetime | None
    season_code: str | None
    competition_name: str | None
    home_name: str | None
    away_name: str | None
    score_home: int | None
    score_away: int | None
    result_type: str | None

    @property
    def score_text(self) -> str:
        return format_score(self.score_home, self.score_away, self.result_type)


@dataclass(frozen=True)
class VenueMatchPage:
    items: tuple[VenueMatchItem, ...]
    total: int
    filters: VenueMatchFilters

    @property
    def has_previous(self) -> bool:
        return self.filters.page > 1

    @property
    def has_next(self) -> bool:
        return self.filters.page * self.filters.page_size < self.total


@dataclass(frozen=True)
class VenuePlayerFilters:
    query: str | None = None
    sort: Sort = DEFAULT_VENUE_PLAYER_SORT
    page: int = 1
    page_size: int = 50

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page must be >= 1")
        if not 1 <= self.page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")


@dataclass(frozen=True)
class VenuePlayerItem:
    player_id: int
    display_name: str
    matches: int
    first_at: datetime | None
    last_at: datetime | None
    goals: int | None
    teams: str | None

    @property
    def goals_per_match(self) -> float | None:
        if self.goals is None or self.matches <= 0:
            return None
        return self.goals / self.matches

    @property
    def goals_per_match_text(self) -> str:
        value = self.goals_per_match
        return "—" if value is None else f"{value:.2f}"


@dataclass(frozen=True)
class VenuePlayerPage:
    items: tuple[VenuePlayerItem, ...]
    total: int
    filters: VenuePlayerFilters

    @property
    def has_previous(self) -> bool:
        return self.filters.page > 1

    @property
    def has_next(self) -> bool:
        return self.filters.page * self.filters.page_size < self.total


@dataclass(frozen=True)
class VenueProfile:
    id: int
    name: str
    city: str | None
    country_code: str | None
    country_name: str | None
    first_match_at: datetime | None
    last_match_at: datetime | None
    matches: int
    played_matches: int
    seasons: int
    competitions: int
    teams: int
    players: int


@dataclass(frozen=True)
class VenueMatchFact:
    match_id: int
    kickoff_at: datetime | None
    season_code: str
    year_start: int
    competition_id: int
    competition_name: str
    home_club_id: int | None
    away_club_id: int | None
    home_name: str | None
    away_name: str | None
    score_home: int | None
    score_away: int | None
    result_type: str | None
    spectators: int | None


@dataclass(frozen=True)
class VenueStats:
    seasons: CountSeries
    competitions: CountSeries
    result_profile: CountSeries
    goal_totals: tuple[int, ...]
    mean_goals: float | None
    median_goals: float | None
    histogram: CountSeries
    months: CountSeries
    weekdays: CountSeries
    heatmap: Heatmap
    attendance_known: int
    attendance_total: int
    attendance_completeness: float | None
    mean_attendance: float | None
    records: tuple[MatchRecord, ...]
    teams: CountSeries
    players: CountSeries
    scorers: CountSeries
    expanded: frozenset[str]

    def is_expanded(self, key: str) -> bool:
        return key in self.expanded

    @property
    def completeness_text(self) -> str:
        return format_percentage(self.attendance_completeness) or "—"


@dataclass(frozen=True)
class VenueCard:
    profile: VenueProfile
    matches: VenueMatchPage
    match_options: VenueMatchFilterOptions
    players: VenuePlayerPage
    stats: VenueStats
