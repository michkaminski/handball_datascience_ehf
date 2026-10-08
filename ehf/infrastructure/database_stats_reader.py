from __future__ import annotations

from collections.abc import Callable

from psycopg import Connection, Error
from psycopg.rows import dict_row

from ehf.domain.database_stats import (
    DatabaseStatsSnapshot,
    DatabaseSummary,
    TableStatItem,
)
from ehf.domain.errors import DataReadError

TABLES_SQL = """
SELECT
    s.schemaname AS schema_name,
    s.relname AS table_name,
    GREATEST(COALESCE(s.n_live_tup, 0), 0)::bigint AS row_count,
    pg_total_relation_size(s.relid)::bigint AS total_bytes,
    pg_relation_size(s.relid)::bigint AS data_bytes,
    pg_indexes_size(s.relid)::bigint AS index_bytes
FROM pg_stat_user_tables s
ORDER BY s.schemaname, s.relname
"""

SUMMARY_SQL = """
SELECT
    current_database() AS name,
    pg_database_size(current_database())::bigint AS size_bytes
"""


class PsycopgDatabaseStatsReader:
    def __init__(self, connect: Callable[[], Connection]) -> None:
        self._connect = connect

    def fetch_snapshot(self) -> DatabaseStatsSnapshot:
        try:
            with self._connect() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(TABLES_SQL)
                    rows = cursor.fetchall()
                    cursor.execute(SUMMARY_SQL)
                    summary_row = cursor.fetchone()
        except Error as exc:
            raise DataReadError(f"Could not read database stats: {exc}") from exc
        tables = tuple(
            TableStatItem(
                schema=row["schema_name"],
                table=row["table_name"],
                rows=int(row["row_count"] or 0),
                total_bytes=int(row["total_bytes"] or 0),
                data_bytes=int(row["data_bytes"] or 0),
                index_bytes=int(row["index_bytes"] or 0),
            )
            for row in rows
        )
        schemas = tuple(sorted({item.schema for item in tables}))
        summary = DatabaseSummary(
            name=str(summary_row["name"]),
            size_bytes=int(summary_row["size_bytes"] or 0),
            table_count=len(tables),
            row_total=sum(item.rows for item in tables),
            tables_bytes=sum(item.total_bytes for item in tables),
            indexes_bytes=sum(item.index_bytes for item in tables),
        )
        return DatabaseStatsSnapshot(summary, tables, schemas)
