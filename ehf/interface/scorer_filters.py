from __future__ import annotations

from typing import Mapping

from ehf.domain.scorers import DEFAULT_SCORER_SORT, ScorerFilters
from ehf.domain.sorting import SCORER_SORT_COLUMNS
from ehf.interface.query_args import optional_int, sort_from_args


def scorer_filters_from_args(args: Mapping[str, str]) -> ScorerFilters:
    return ScorerFilters(
        season_id=optional_int(args.get("season_id")),
        competition_id=optional_int(args.get("competition_id")),
        sort=sort_from_args(args, SCORER_SORT_COLUMNS, DEFAULT_SCORER_SORT),
        page=optional_int(args.get("page")) or 1,
    )
