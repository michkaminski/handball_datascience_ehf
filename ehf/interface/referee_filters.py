from __future__ import annotations

from typing import Mapping

from ehf.domain.referees import RefereeFilters, RefereeMatchFilters
from ehf.domain.sorting import (
    DEFAULT_REFEREE_MATCH_SORT,
    DEFAULT_REFEREE_SORT,
    REFEREE_MATCH_SORT_COLUMNS,
    REFEREE_SORT_COLUMNS,
)
from ehf.interface.query_args import optional_date, optional_int, optional_text, sort_from_args


def referee_filters_from_args(args: Mapping[str, str]) -> RefereeFilters:
    return RefereeFilters(
        query=optional_text(args.get("q")),
        country=optional_text(args.get("country")),
        sort=sort_from_args(args, REFEREE_SORT_COLUMNS, DEFAULT_REFEREE_SORT),
        page=optional_int(args.get("page")) or 1,
    )


def referee_match_filters_from_args(args: Mapping[str, str]) -> RefereeMatchFilters:
    return RefereeMatchFilters(
        season_id=optional_int(args.get("season_id")),
        competition_id=optional_int(args.get("competition_id")),
        club_id=optional_int(args.get("club_id")),
        side=optional_text(args.get("side")),
        date_from=optional_date(args.get("date_from")),
        date_to=optional_date(args.get("date_to")),
        sort=sort_from_args(args, REFEREE_MATCH_SORT_COLUMNS, DEFAULT_REFEREE_MATCH_SORT),
        page=optional_int(args.get("page")) or 1,
    )
