from __future__ import annotations

from typing import Mapping

from ehf.domain.matches import MatchFilters
from ehf.domain.sorting import DEFAULT_MATCH_SORT, MATCH_SORT_COLUMNS
from ehf.interface.query_args import optional_date, optional_int, optional_text, sort_from_args


def match_filters_from_args(args: Mapping[str, str]) -> MatchFilters:
    return MatchFilters(
        season_id=optional_int(args.get("season_id")),
        competition_id=optional_int(args.get("competition_id")),
        phase=optional_text(args.get("phase")),
        group_code=optional_text(args.get("group_code")),
        venue_id=optional_int(args.get("venue_id")),
        club_query=optional_text(args.get("club")),
        match_date=optional_date(args.get("date")),
        sort=sort_from_args(args, MATCH_SORT_COLUMNS, DEFAULT_MATCH_SORT),
        page=optional_int(args.get("page")) or 1,
    )
