from __future__ import annotations

from typing import Mapping

from ehf.domain.seasons import DEFAULT_SEASON_SORT, SeasonFilters
from ehf.domain.sorting import SEASON_SORT_COLUMNS
from ehf.interface.query_args import optional_int, optional_text, sort_from_args


def season_filters_from_args(args: Mapping[str, str]) -> SeasonFilters:
    return SeasonFilters(
        query=optional_text(args.get("q")),
        state=optional_text(args.get("state")),
        sort=sort_from_args(args, SEASON_SORT_COLUMNS, DEFAULT_SEASON_SORT),
        page=optional_int(args.get("page")) or 1,
    )
