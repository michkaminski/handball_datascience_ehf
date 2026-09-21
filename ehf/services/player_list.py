from __future__ import annotations

from typing import Protocol

from ehf.domain.players import PlayerFilterOptions, PlayerFilters, PlayerListPage


class PlayerListReader(Protocol):
    def fetch_page(self, filters: PlayerFilters) -> PlayerListPage: ...

    def fetch_options(self) -> PlayerFilterOptions: ...


class PlayerListService:
    def __init__(self, reader: PlayerListReader) -> None:
        self._reader = reader

    def list_players(self, filters: PlayerFilters) -> PlayerListPage:
        return self._reader.fetch_page(filters)

    def filter_options(self) -> PlayerFilterOptions:
        return self._reader.fetch_options()
