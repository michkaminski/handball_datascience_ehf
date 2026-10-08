from __future__ import annotations

from typing import Mapping

from ehf.domain.database_stats import DEFAULT_DATABASE_STATS_SORT, DatabaseStatsFilters
from ehf.domain.sorting import DATABASE_STATS_SORT_COLUMNS
from ehf.interface.query_args import optional_int, optional_text, sort_from_args


def database_stats_filters_from_args(args: Mapping[str, str]) -> DatabaseStatsFilters:
    return DatabaseStatsFilters(
        query=optional_text(args.get("q")),
        schema=optional_text(args.get("schema")),
        fill=optional_text(args.get("fill")),
        min_rows=optional_int(args.get("min_rows")),
        sort=sort_from_args(args, DATABASE_STATS_SORT_COLUMNS, DEFAULT_DATABASE_STATS_SORT),
    )
