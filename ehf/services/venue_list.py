from __future__ import annotations

from typing import Protocol

from ehf.domain.venues import VenueFilterOptions, VenueFilters, VenueListPage


class VenueListReader(Protocol):
    def fetch_page(self, filters: VenueFilters) -> VenueListPage: ...

    def fetch_options(self) -> VenueFilterOptions: ...


class VenueListService:
    def __init__(self, reader: VenueListReader) -> None:
        self._reader = reader

    def list_venues(self, filters: VenueFilters) -> VenueListPage:
        return self._reader.fetch_page(filters)

    def filter_options(self) -> VenueFilterOptions:
        return self._reader.fetch_options()
