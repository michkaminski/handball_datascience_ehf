from __future__ import annotations

from typing import Mapping

from ehf.domain.gender import GENDERS
from ehf.domain.goal_distribution import GoalDistributionFilters
from ehf.interface.query_args import optional_int, optional_text


def goal_distribution_filters_from_args(args: Mapping[str, str]) -> GoalDistributionFilters:
    gender = optional_text(args.get("gender"))
    if gender is not None and gender not in GENDERS:
        raise ValueError("gender must be men or women")
    return GoalDistributionFilters(
        season_id=optional_int(args.get("season")),
        competition_id=optional_int(args.get("competition")),
        gender=gender,
    )
