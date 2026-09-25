from __future__ import annotations

from typing import Protocol

from ehf.domain.competitions import (
    CompetitionFilterOptions,
    CompetitionFilters,
    CompetitionListPage,
)


class CompetitionListReader(Protocol):
    def fetch_page(self, filters: CompetitionFilters) -> CompetitionListPage: ...

    def fetch_options(self) -> CompetitionFilterOptions: ...


class CompetitionListService:
    def __init__(self, reader: CompetitionListReader) -> None:
        self._reader = reader

    def list_competitions(self, filters: CompetitionFilters) -> CompetitionListPage:
        return self._reader.fetch_page(filters)

    def filter_options(self) -> CompetitionFilterOptions:
        return self._reader.fetch_options()
