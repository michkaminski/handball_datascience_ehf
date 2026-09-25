from __future__ import annotations

from typing import Protocol

from ehf.domain.scorers import ScorerFilterOptions, ScorerFilters, ScorerListPage


class ScorerListReader(Protocol):
    def fetch_page(self, filters: ScorerFilters) -> ScorerListPage: ...

    def fetch_options(self) -> ScorerFilterOptions: ...


class ScorerListService:
    def __init__(self, reader: ScorerListReader) -> None:
        self._reader = reader

    def list_scorers(self, filters: ScorerFilters) -> ScorerListPage:
        return self._reader.fetch_page(filters)

    def filter_options(self) -> ScorerFilterOptions:
        return self._reader.fetch_options()
