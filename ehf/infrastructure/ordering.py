from __future__ import annotations

from collections.abc import Mapping

from ehf.domain.sorting import Sort


def order_sql(sort: Sort, columns: Mapping[str, tuple[str, ...]], tiebreaker: str) -> str:
    direction = "DESC NULLS LAST" if sort.descending else "ASC NULLS LAST"
    expressions = columns[sort.column]
    parts = [f"{item} {direction}" for item in expressions]
    parts.append(tiebreaker)
    return "ORDER BY " + ", ".join(parts)
