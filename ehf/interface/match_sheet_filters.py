from __future__ import annotations

from datetime import time
from typing import Mapping

from ehf.domain.match_sheet import MatchSheetRequest, SheetOrder
from ehf.interface.query_args import optional_date, optional_int, optional_text


def match_sheet_request_from_args(args: Mapping[str, str]) -> MatchSheetRequest:
    kickoff = optional_text(args.get("time"))
    return MatchSheetRequest(
        season_id=optional_int(args.get("season_id")),
        competition_id=optional_int(args.get("competition_id")),
        home_id=optional_int(args.get("home_id")),
        away_id=optional_int(args.get("away_id")),
        match_date=optional_date(args.get("date")),
        kickoff=time.fromisoformat(kickoff) if kickoff else None,
        venue_id=optional_int(args.get("venue_id")),
        order=SheetOrder(optional_text(args.get("order")) or SheetOrder.POSITIONS.value),
        previous_season=optional_text(args.get("previous")) == "1",
    )
