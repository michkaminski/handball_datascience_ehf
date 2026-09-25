from __future__ import annotations

from dataclasses import dataclass

from ehf.domain.gender import GENDERS, gender_label
from ehf.domain.matches import Choice
from ehf.domain.sorting import Sort

DEFAULT_COMPETITION_SORT = Sort("season", True)


@dataclass(frozen=True)
class CompetitionFilters:
    query: str | None = None
    season_id: int | None = None
    sort: Sort = DEFAULT_COMPETITION_SORT
    page: int = 1
    page_size: int = 50

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page must be >= 1")
        if not 1 <= self.page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")


@dataclass(frozen=True)
class CompetitionFilterOptions:
    seasons: tuple[Choice, ...]


@dataclass(frozen=True)
class CompetitionListItem:
    id: int
    competition_id: int
    season_id: int
    season_code: str
    name: str
    gender: str
    teams: int
    matches: int

    @property
    def gender_label(self) -> str:
        if self.gender not in GENDERS:
            return self.gender
        return gender_label(self.gender)


@dataclass(frozen=True)
class CompetitionListPage:
    items: tuple[CompetitionListItem, ...]
    total: int
    filters: CompetitionFilters

    @property
    def has_previous(self) -> bool:
        return self.filters.page > 1

    @property
    def has_next(self) -> bool:
        return self.filters.page * self.filters.page_size < self.total
