from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Measure(StrEnum):
    FILL = "fill"
    COUNT = "count"


@dataclass(frozen=True)
class MatchRecord:
    match_id: int
    kickoff: datetime | None
    season_key: str
    season_order: int
    competition_key: str
    competition_name: str
    host_id: int
    host_name: str
    opponent_id: int
    opponent_name: str
    venue_id: int | None
    venue_name: str | None
    spectators: int | None
    capacity: int | None
    phase: str | None
    host_goals: int | None
    opponent_goals: int | None


@dataclass(frozen=True)
class CapacityOverride:
    venue_id: int | None
    season_key: str | None
    match_id: int | None
    capacity: int
    note: str = ""


@dataclass(frozen=True)
class ClubLineage:
    previous_id: int
    current_id: int
    note: str = ""


@dataclass(frozen=True)
class ModelSpec:
    key: str
    label: str
    measure: Measure
    scope: str
    reference_seasons: int = 3
    holdout_seasons: int = 2
    min_matches_reliable: int = 6
    max_ci_width_reliable: float = 60.0
