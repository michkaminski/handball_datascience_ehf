from __future__ import annotations

from typing import Protocol

from ehf.domain.matches import MatchFilterOptions, MatchFilters, MatchListPage


class MatchListReader(Protocol):
    def fetch_page(self, filters: MatchFilters) -> MatchListPage: ...

    def fetch_options(self) -> MatchFilterOptions: ...


class MatchListService:
    def __init__(self, reader: MatchListReader) -> None:
        self._reader = reader

    def list_matches(self, filters: MatchFilters) -> MatchListPage:
        return self._reader.fetch_page(filters)

    def filter_options(self) -> MatchFilterOptions:
        return self._reader.fetch_options()
