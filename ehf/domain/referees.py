from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from ehf.domain.counts import CountSeries, Heatmap
from ehf.domain.matches import Choice, format_score
from ehf.domain.sorting import DEFAULT_REFEREE_MATCH_SORT, DEFAULT_REFEREE_SORT, Sort


@dataclass(frozen=True)
class RefereeFilters:
    query: str | None = None
    country: str | None = None
    sort: Sort = DEFAULT_REFEREE_SORT
    page: int = 1
    page_size: int = 50

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page must be >= 1")
        if not 1 <= self.page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")


@dataclass(frozen=True)
class RefereeFilterOptions:
    countries: tuple[Choice, ...]


@dataclass(frozen=True)
class RefereeListItem:
    id: int
    display_name: str
    first_name: str | None
    last_name: str | None
    country_code: str | None
    country_name: str | None
    matches: int


@dataclass(frozen=True)
class RefereeListPage:
    items: tuple[RefereeListItem, ...]
    total: int
    filters: RefereeFilters

    @property
    def has_previous(self) -> bool:
        return self.filters.page > 1

    @property
    def has_next(self) -> bool:
        return self.filters.page * self.filters.page_size < self.total


@dataclass(frozen=True)
class RefereeMatchFilters:
    season_id: int | None = None
    competition_id: int | None = None
    club_id: int | None = None
    side: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    sort: Sort = DEFAULT_REFEREE_MATCH_SORT
    page: int = 1
    page_size: int = 50

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page must be >= 1")
        if not 1 <= self.page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        if self.side not in {None, "home", "away"}:
            raise ValueError("side must be home or away")


@dataclass(frozen=True)
class RefereeMatchFilterOptions:
    seasons: tuple[Choice, ...]
    competitions: tuple[Choice, ...]
    clubs: tuple[Choice, ...]


@dataclass(frozen=True)
class RefereeMatchItem:
    match_id: int
    kickoff_at: datetime | None
    season_code: str | None
    competition_name: str | None
    home_name: str | None
    away_name: str | None
    score_home: int | None
    score_away: int | None
    result_type: str | None
    partner_id: int | None
    partner_name: str | None

    @property
    def score_text(self) -> str:
        return format_score(self.score_home, self.score_away, self.result_type)


@dataclass(frozen=True)
class RefereeMatchPage:
    items: tuple[RefereeMatchItem, ...]
    total: int
    filters: RefereeMatchFilters

    @property
    def has_previous(self) -> bool:
        return self.filters.page > 1

    @property
    def has_next(self) -> bool:
        return self.filters.page * self.filters.page_size < self.total


@dataclass(frozen=True)
class RefereeSeasonRow:
    season_code: str
    matches: int
    competitions: str | None


@dataclass(frozen=True)
class RefereeProfile:
    id: int
    display_name: str
    first_name: str | None
    last_name: str | None
    source_name: str | None
    country_code: str | None
    country_name: str | None
    first_match_at: datetime | None
    last_match_at: datetime | None
    matches: int
    played_matches: int
    seasons: int
    competitions: int
    teams: int
    seasons_activity: tuple[RefereeSeasonRow, ...]


@dataclass(frozen=True)
class RefereeMatchFact:
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
    partner_id: int | None
    partner_name: str | None


@dataclass(frozen=True)
class RefereeStats:
    seasons: CountSeries
    competitions: CountSeries
    season_competitions: CountSeries
    teams: CountSeries
    home_teams: CountSeries
    away_teams: CountSeries
    partners: CountSeries
    months: CountSeries
    weekdays: CountSeries
    heatmap: Heatmap
    distinct_teams: int
    distinct_competitions: int
    expanded: frozenset[str]

    def is_expanded(self, key: str) -> bool:
        return key in self.expanded


@dataclass(frozen=True)
class RefereeCard:
    profile: RefereeProfile
    matches: RefereeMatchPage
    match_options: RefereeMatchFilterOptions
    stats: RefereeStats
