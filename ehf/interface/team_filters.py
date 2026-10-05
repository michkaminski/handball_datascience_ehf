from __future__ import annotations

from typing import Mapping

from ehf.domain.sorting import TEAM_SORT_COLUMNS
from ehf.domain.team_detail import TeamDetailFilters, TeamSheetFilters
from ehf.domain.teams import DEFAULT_TEAM_SORT, TeamFilters
from ehf.interface.query_args import optional_int, optional_text, sort_from_args


def team_filters_from_args(args: Mapping[str, str]) -> TeamFilters:
    return TeamFilters(
        query=optional_text(args.get("q")),
        season_id=optional_int(args.get("season_id")),
        gender=optional_text(args.get("gender")),
        sort=sort_from_args(args, TEAM_SORT_COLUMNS, DEFAULT_TEAM_SORT),
        page=optional_int(args.get("page")) or 1,
    )


def team_detail_filters_from_args(args: Mapping[str, str]) -> TeamDetailFilters:
    return TeamDetailFilters(
        season_id=optional_int(args.get("season_id")),
        competition_id=optional_int(args.get("competition_id")),
        opponent=optional_text(args.get("opponent")),
        player=optional_text(args.get("player")),
        played_only=optional_text(args.get("played")) == "1",
    )


def team_sheet_filters_from_args(args: Mapping[str, str]) -> TeamSheetFilters:
    return TeamSheetFilters(
        season_id=optional_int(args.get("sheet_season_id")),
        competition_id=optional_int(args.get("sheet_competition_id")),
        opponent=optional_text(args.get("sheet_opponent")),
    )
