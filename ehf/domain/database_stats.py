from __future__ import annotations

from dataclasses import dataclass

from ehf.domain.matches import Choice
from ehf.domain.sorting import DATABASE_STATS_SORT_COLUMNS, Sort

DEFAULT_DATABASE_STATS_SORT = Sort("total", True)
FILL_STATES = frozenset({"empty", "nonempty"})
FILL_STATE_CHOICES = (
    Choice("nonempty", "Tylko z danymi"),
    Choice("empty", "Tylko puste"),
)


def format_bytes(size: int) -> str:
    value = float(max(0, size))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            text = f"{value:.1f}".rstrip("0").rstrip(".")
            return f"{text} {unit}"
        value /= 1024
    return f"{int(size)} B"


def format_count(value: int) -> str:
    return f"{value:,}".replace(",", " ")


@dataclass(frozen=True)
class DatabaseStatsFilters:
    query: str | None = None
    schema: str | None = None
    fill: str | None = None
    min_rows: int | None = None
    sort: Sort = DEFAULT_DATABASE_STATS_SORT

    def __post_init__(self) -> None:
        if self.fill is not None and self.fill not in FILL_STATES:
            raise ValueError("fill must be empty or nonempty")
        if self.min_rows is not None and self.min_rows < 0:
            raise ValueError("min_rows must be >= 0")
        if self.sort.column not in DATABASE_STATS_SORT_COLUMNS:
            raise ValueError("unsupported sort column")


@dataclass(frozen=True)
class TableStatItem:
    schema: str
    table: str
    rows: int
    total_bytes: int
    data_bytes: int
    index_bytes: int

    @property
    def full_name(self) -> str:
        return f"{self.schema}.{self.table}"

    @property
    def rows_label(self) -> str:
        return format_count(self.rows)

    @property
    def total_label(self) -> str:
        return format_bytes(self.total_bytes)

    @property
    def data_label(self) -> str:
        return format_bytes(self.data_bytes)

    @property
    def indexes_label(self) -> str:
        return format_bytes(self.index_bytes)


@dataclass(frozen=True)
class DatabaseSummary:
    name: str
    size_bytes: int
    table_count: int
    row_total: int
    tables_bytes: int
    indexes_bytes: int

    @property
    def size_label(self) -> str:
        return format_bytes(self.size_bytes)

    @property
    def table_count_label(self) -> str:
        return format_count(self.table_count)

    @property
    def row_total_label(self) -> str:
        return format_count(self.row_total)

    @property
    def tables_bytes_label(self) -> str:
        return format_bytes(self.tables_bytes)

    @property
    def indexes_bytes_label(self) -> str:
        return format_bytes(self.indexes_bytes)


@dataclass(frozen=True)
class DatabaseStatsSnapshot:
    summary: DatabaseSummary
    tables: tuple[TableStatItem, ...]
    schemas: tuple[str, ...]


@dataclass(frozen=True)
class DatabaseStatsFilterOptions:
    schemas: tuple[Choice, ...]
    fills: tuple[Choice, ...] = FILL_STATE_CHOICES


@dataclass(frozen=True)
class DatabaseStatsPage:
    summary: DatabaseSummary
    items: tuple[TableStatItem, ...]
    schemas: tuple[str, ...]
    filters: DatabaseStatsFilters
    filtered_count: int

    @property
    def filtered_count_label(self) -> str:
        return format_count(self.filtered_count)


def filter_tables(
    tables: tuple[TableStatItem, ...],
    filters: DatabaseStatsFilters,
) -> tuple[TableStatItem, ...]:
    items = list(tables)
    if filters.query:
        needle = filters.query.casefold()
        items = [
            item
            for item in items
            if needle in item.schema.casefold()
            or needle in item.table.casefold()
            or needle in item.full_name.casefold()
        ]
    if filters.schema:
        items = [item for item in items if item.schema == filters.schema]
    if filters.fill == "empty":
        items = [item for item in items if item.rows == 0]
    elif filters.fill == "nonempty":
        items = [item for item in items if item.rows > 0]
    if filters.min_rows is not None:
        items = [item for item in items if item.rows >= filters.min_rows]
    key = {
        "schema": lambda item: item.schema.casefold(),
        "table": lambda item: item.table.casefold(),
        "rows": lambda item: item.rows,
        "total": lambda item: item.total_bytes,
        "data": lambda item: item.data_bytes,
        "indexes": lambda item: item.index_bytes,
    }[filters.sort.column]
    items.sort(key=key, reverse=filters.sort.descending)
    return tuple(items)
