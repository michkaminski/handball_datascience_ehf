from __future__ import annotations

from dataclasses import dataclass

from ehf.domain.matches import Choice
from ehf.domain.sorting import Sort

SEASON_STATES = frozenset({"complete", "open", "empty"})
SEASON_STATE_LABELS = {
    "complete": "Kompletny",
    "open": "W toku",
    "empty": "Pusty",
}
SEASON_STATE_CHOICES = tuple(
    Choice(code, SEASON_STATE_LABELS[code]) for code in ("complete", "open", "empty")
)
DEFAULT_SEASON_SORT = Sort("year", True)


@dataclass(frozen=True)
class SeasonFilters:
    query: str | None = None
    state: str | None = None
    sort: Sort = DEFAULT_SEASON_SORT
    page: int = 1
    page_size: int = 50

    def __post_init__(self) -> None:
        if self.state is not None and self.state not in SEASON_STATES:
            raise ValueError("state must be complete, open, or empty")
        if self.page < 1:
            raise ValueError("page must be >= 1")
        if not 1 <= self.page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")


@dataclass(frozen=True)
class SeasonFilterOptions:
    states: tuple[Choice, ...]


@dataclass(frozen=True)
class SeasonListItem:
    id: int
    code: str
    year_start: int
    competitions: int
    matches: int
    state: str

    @property
    def state_label(self) -> str:
        return SEASON_STATE_LABELS.get(self.state, self.state)


@dataclass(frozen=True)
class SeasonListPage:
    items: tuple[SeasonListItem, ...]
    total: int
    filters: SeasonFilters

    @property
    def has_previous(self) -> bool:
        return self.filters.page > 1

    @property
    def has_next(self) -> bool:
        return self.filters.page * self.filters.page_size < self.total
