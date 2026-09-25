from __future__ import annotations

from typing import Mapping

from ehf.domain.competitions import DEFAULT_COMPETITION_SORT, CompetitionFilters
from ehf.domain.sorting import COMPETITION_SORT_COLUMNS
from ehf.interface.query_args import optional_int, optional_text, sort_from_args


def competition_filters_from_args(args: Mapping[str, str]) -> CompetitionFilters:
    return CompetitionFilters(
        query=optional_text(args.get("q")),
        season_id=optional_int(args.get("season_id")),
        sort=sort_from_args(args, COMPETITION_SORT_COLUMNS, DEFAULT_COMPETITION_SORT),
        page=optional_int(args.get("page")) or 1,
    )
