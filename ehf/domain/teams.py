from __future__ import annotations

from dataclasses import dataclass

from ehf.domain.gender import GENDERS, gender_label
from ehf.domain.matches import Choice
from ehf.domain.sorting import Sort

TEAM_STATUS_LABELS = {"active": "Aktywna", "listed": "Bez meczów"}
DEFAULT_TEAM_SORT = Sort("season", True)


@dataclass(frozen=True)
class TeamFilters:
    query: str | None = None
    season_id: int | None = None
    gender: str | None = None
    sort: Sort = DEFAULT_TEAM_SORT
    page: int = 1
    page_size: int = 50

    def __post_init__(self) -> None:
        if self.gender is not None and self.gender not in GENDERS:
            raise ValueError("gender must be men or women")
        if self.page < 1:
            raise ValueError("page must be >= 1")
        if not 1 <= self.page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")


@dataclass(frozen=True)
class TeamFilterOptions:
    seasons: tuple[Choice, ...]
    genders: tuple[Choice, ...]


@dataclass(frozen=True)
class TeamListItem:
    id: int
    season_id: int
    season_code: str
    name: str
    genders: str
    city: str | None
    matches: int
    status: str

    @property
    def gender_label(self) -> str:
        return gender_label(self.genders)

    @property
    def status_label(self) -> str:
        return TEAM_STATUS_LABELS.get(self.status, self.status)


@dataclass(frozen=True)
class TeamListPage:
    items: tuple[TeamListItem, ...]
    total: int
    filters: TeamFilters

    @property
    def has_previous(self) -> bool:
        return self.filters.page > 1

    @property
    def has_next(self) -> bool:
        return self.filters.page * self.filters.page_size < self.total
