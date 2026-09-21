from __future__ import annotations

from typing import Protocol

from ehf.domain.referees import RefereeFilterOptions, RefereeFilters, RefereeListPage


class RefereeListReader(Protocol):
    def fetch_page(self, filters: RefereeFilters) -> RefereeListPage: ...

    def fetch_options(self) -> RefereeFilterOptions: ...


class RefereeListService:
    def __init__(self, reader: RefereeListReader) -> None:
        self._reader = reader

    def list_referees(self, filters: RefereeFilters) -> RefereeListPage:
        return self._reader.fetch_page(filters)

    def filter_options(self) -> RefereeFilterOptions:
        return self._reader.fetch_options()
