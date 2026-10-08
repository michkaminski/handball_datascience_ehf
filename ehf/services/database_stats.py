from __future__ import annotations

from typing import Protocol

from ehf.domain.database_stats import (
    FILL_STATE_CHOICES,
    DatabaseStatsFilterOptions,
    DatabaseStatsFilters,
    DatabaseStatsPage,
    DatabaseStatsSnapshot,
    filter_tables,
)
from ehf.domain.matches import Choice


class DatabaseStatsReader(Protocol):
    def fetch_snapshot(self) -> DatabaseStatsSnapshot: ...


class DatabaseStatsService:
    def __init__(self, reader: DatabaseStatsReader) -> None:
        self._reader = reader

    def list_stats(self, filters: DatabaseStatsFilters) -> DatabaseStatsPage:
        snapshot = self._reader.fetch_snapshot()
        items = filter_tables(snapshot.tables, filters)
        return DatabaseStatsPage(
            summary=snapshot.summary,
            items=items,
            schemas=snapshot.schemas,
            filters=filters,
            filtered_count=len(items),
        )

    def filter_options(self, schemas: tuple[str, ...]) -> DatabaseStatsFilterOptions:
        return DatabaseStatsFilterOptions(
            schemas=tuple(Choice(name, name) for name in schemas),
            fills=FILL_STATE_CHOICES,
        )
