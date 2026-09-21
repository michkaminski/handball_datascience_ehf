from __future__ import annotations

from datetime import date
from typing import Mapping

from ehf.domain.matches import MatchFilters


def match_filters_from_args(args: Mapping[str, str]) -> MatchFilters:
    return MatchFilters(
        season_id=_optional_int(args.get("season_id")),
        competition_id=_optional_int(args.get("competition_id")),
        phase=_optional_text(args.get("phase")),
        group_code=_optional_text(args.get("group_code")),
        venue_id=_optional_int(args.get("venue_id")),
        club_query=_optional_text(args.get("club")),
        match_date=_optional_date(args.get("date")),
        page=_optional_int(args.get("page")) or 1,
    )


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _optional_int(value: str | None) -> int | None:
    text = _optional_text(value)
    if text is None:
        return None
    return int(text)


def _optional_date(value: str | None) -> date | None:
    text = _optional_text(value)
    if text is None:
        return None
    return date.fromisoformat(text)
