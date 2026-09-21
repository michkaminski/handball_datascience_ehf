from __future__ import annotations

from typing import Mapping

from ehf.domain.players import PlayerFilters, PlayerMatchFilters
from ehf.domain.sorting import (
    DEFAULT_PLAYER_MATCH_SORT,
    DEFAULT_PLAYER_SORT,
    PLAYER_MATCH_SORT_COLUMNS,
    PLAYER_SORT_COLUMNS,
)
from ehf.interface.query_args import optional_date, optional_int, optional_text, sort_from_args


def player_filters_from_args(args: Mapping[str, str]) -> PlayerFilters:
    return PlayerFilters(
        season_id=optional_int(args.get("season_id")),
        competition_id=optional_int(args.get("competition_id")),
        club_id=optional_int(args.get("club_id")),
        position=optional_text(args.get("position")),
        birth_year=optional_int(args.get("birth_year")),
        query=optional_text(args.get("q")),
        sort=sort_from_args(args, PLAYER_SORT_COLUMNS, DEFAULT_PLAYER_SORT),
        page=optional_int(args.get("page")) or 1,
    )


def player_match_filters_from_args(args: Mapping[str, str]) -> PlayerMatchFilters:
    return PlayerMatchFilters(
        season_id=optional_int(args.get("season_id")),
        competition_id=optional_int(args.get("competition_id")),
        club_id=optional_int(args.get("club_id")),
        match_date=optional_date(args.get("date")),
        sort=sort_from_args(args, PLAYER_MATCH_SORT_COLUMNS, DEFAULT_PLAYER_MATCH_SORT),
        page=optional_int(args.get("page")) or 1,
    )
