from __future__ import annotations

from typing import Protocol

from ehf.domain.seasons import SEASON_STATE_CHOICES, SeasonFilterOptions, SeasonFilters, SeasonListPage


class SeasonListReader(Protocol):
    def fetch_page(self, filters: SeasonFilters) -> SeasonListPage: ...


class SeasonListService:
    def __init__(self, reader: SeasonListReader) -> None:
        self._reader = reader

    def list_seasons(self, filters: SeasonFilters) -> SeasonListPage:
        return self._reader.fetch_page(filters)

    def filter_options(self) -> SeasonFilterOptions:
        return SeasonFilterOptions(states=SEASON_STATE_CHOICES)
