from __future__ import annotations

from typing import Mapping

from ehf.domain.sorting import (
    DEFAULT_VENUE_MATCH_SORT,
    DEFAULT_VENUE_PLAYER_SORT,
    DEFAULT_VENUE_SORT,
    VENUE_MATCH_SORT_COLUMNS,
    VENUE_PLAYER_SORT_COLUMNS,
    VENUE_SORT_COLUMNS,
)
from ehf.domain.venues import VenueFilters, VenueMatchFilters, VenuePlayerFilters
from ehf.interface.query_args import optional_int, optional_text, sort_from_args


def venue_filters_from_args(args: Mapping[str, str]) -> VenueFilters:
    return VenueFilters(
        query=optional_text(args.get("q")),
        city=optional_text(args.get("city")),
        sort=sort_from_args(args, VENUE_SORT_COLUMNS, DEFAULT_VENUE_SORT),
        page=optional_int(args.get("page")) or 1,
    )


def venue_match_filters_from_args(args: Mapping[str, str]) -> VenueMatchFilters:
    return VenueMatchFilters(
        season_id=optional_int(args.get("season_id")),
        competition_id=optional_int(args.get("competition_id")),
        club_id=optional_int(args.get("club_id")),
        sort=sort_from_args(args, VENUE_MATCH_SORT_COLUMNS, DEFAULT_VENUE_MATCH_SORT),
        page=optional_int(args.get("page")) or 1,
    )


def venue_player_filters_from_args(args: Mapping[str, str]) -> VenuePlayerFilters:
    return VenuePlayerFilters(
        query=optional_text(args.get("player_q")),
        sort=sort_from_args(
            args, VENUE_PLAYER_SORT_COLUMNS, DEFAULT_VENUE_PLAYER_SORT, "player_sort", "player_dir"
        ),
        page=optional_int(args.get("player_page")) or 1,
    )
