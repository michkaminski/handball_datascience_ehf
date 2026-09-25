from __future__ import annotations

from dataclasses import dataclass

from ehf.domain.matches import Choice
from ehf.domain.sorting import Sort

DEFAULT_SCORER_SORT = Sort("goals", True)


@dataclass(frozen=True)
class ScorerFilters:
    season_id: int | None = None
    competition_id: int | None = None
    sort: Sort = DEFAULT_SCORER_SORT
    page: int = 1
    page_size: int = 50

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page must be >= 1")
        if not 1 <= self.page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")


@dataclass(frozen=True)
class ScorerFilterOptions:
    seasons: tuple[Choice, ...]
    competitions: tuple[Choice, ...]


@dataclass(frozen=True)
class ScorerListItem:
    rank: int
    player_id: int
    display_name: str
    teams: str | None
    goals: int
    matches: int


@dataclass(frozen=True)
class ScorerListPage:
    items: tuple[ScorerListItem, ...]
    total: int
    filters: ScorerFilters

    @property
    def has_previous(self) -> bool:
        return self.filters.page > 1

    @property
    def has_next(self) -> bool:
        return self.filters.page * self.filters.page_size < self.total
