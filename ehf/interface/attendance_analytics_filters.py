from __future__ import annotations

from typing import Mapping

from ehf.domain.attendance_analytics import AttendanceFilters
from ehf.domain.gender import GENDERS
from ehf.interface.query_args import optional_date, optional_int, optional_text

TRUE_VALUES = frozenset({"1", "true", "on", "yes"})


def optional_flag(value: str | None) -> bool:
    text = optional_text(value)
    return text is not None and text.lower() in TRUE_VALUES


def attendance_filters_from_args(args: Mapping[str, str]) -> AttendanceFilters:
    gender = optional_text(args.get("gender"))
    if gender is not None and gender not in GENDERS:
        raise ValueError("gender must be men or women")
    return AttendanceFilters(
        season_id=optional_int(args.get("season")),
        competition_id=optional_int(args.get("competition")),
        gender=gender,
        phase=optional_text(args.get("phase")),
        club_id=optional_int(args.get("club")),
        exclude_zeros=optional_flag(args.get("exclude_zeros")),
        date_from=optional_date(args.get("date_from")),
        date_to=optional_date(args.get("date_to")),
    )
