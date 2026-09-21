from __future__ import annotations

from datetime import date
from typing import Mapping

from ehf.domain.sorting import Sort, resolve_sort


def optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def optional_int(value: str | None) -> int | None:
    text = optional_text(value)
    if text is None:
        return None
    return int(text)


def optional_date(value: str | None) -> date | None:
    text = optional_text(value)
    if text is None:
        return None
    return date.fromisoformat(text)


def sort_from_args(
    args: Mapping[str, str],
    allowed: frozenset[str],
    default: Sort,
    column_key: str = "sort",
    direction_key: str = "dir",
) -> Sort:
    return resolve_sort(
        optional_text(args.get(column_key)),
        optional_text(args.get(direction_key)),
        allowed,
        default,
    )
