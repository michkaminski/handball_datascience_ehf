from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ehf.domain.attendance_analytics import (
    format_optional_int,
    format_rounded,
    format_signed_decimal,
)
from ehf.domain.goal_distribution import format_int, format_share

OPPONENT_LIMIT = 100
OPPONENTS_CLUB_REQUIRED_NOTE = (
    "Select a home club in the filters to rank the opponents it hosted by mean home attendance."
)


@dataclass(frozen=True)
class OpponentAttendance:
    opponent_id: int
    opponent_name: str
    played: int
    known: int
    mean: float | None
    maximum: int | None

    def __post_init__(self) -> None:
        if self.played < 0 or self.known < 0:
            raise ValueError("match counts cannot be negative")
        if self.known > self.played:
            raise ValueError("known matches cannot exceed played matches")

    @property
    def coverage(self) -> float | None:
        if self.played == 0:
            return None
        return self.known / self.played


@dataclass(frozen=True)
class OpponentRow:
    position: int
    opponent: OpponentAttendance
    club_mean: float | None

    @property
    def difference(self) -> float | None:
        if self.opponent.mean is None or self.club_mean is None:
            return None
        return self.opponent.mean - self.club_mean

    @property
    def difference_label(self) -> str:
        return format_signed_decimal(self.difference)

    @property
    def played_label(self) -> str:
        return format_int(self.opponent.played)

    @property
    def known_label(self) -> str:
        return format_int(self.opponent.known)

    @property
    def mean_label(self) -> str:
        return format_rounded(self.opponent.mean)

    @property
    def maximum_label(self) -> str:
        return format_optional_int(self.opponent.maximum)

    @property
    def coverage_label(self) -> str:
        coverage = self.opponent.coverage
        return "—" if coverage is None else format_share(coverage)


@dataclass(frozen=True)
class OpponentSection:
    club_id: int | None
    club_mean: float | None
    rows: tuple[OpponentRow, ...]
    note: str | None = None

    @property
    def requires_club(self) -> bool:
        return self.club_id is None

    @property
    def club_mean_label(self) -> str:
        return format_rounded(self.club_mean)

    @classmethod
    def club_required(cls) -> OpponentSection:
        return cls(club_id=None, club_mean=None, rows=(), note=OPPONENTS_CLUB_REQUIRED_NOTE)


class OpponentCalculator:
    @staticmethod
    def build_section(
        club_id: int,
        opponents: Sequence[OpponentAttendance],
        club_mean: float | None,
        limit: int = OPPONENT_LIMIT,
    ) -> OpponentSection:
        eligible = [item for item in opponents if item.mean is not None]
        eligible.sort(
            key=lambda item: (
                -(item.mean or 0.0),
                -item.known,
                item.opponent_name.casefold(),
                item.opponent_id,
            )
        )
        rows = tuple(
            OpponentRow(position=position, opponent=item, club_mean=club_mean)
            for position, item in enumerate(eligible[:limit], start=1)
        )
        note = None if rows else "No opponents with known home attendance for the selected filters."
        return OpponentSection(club_id=club_id, club_mean=club_mean, rows=rows, note=note)
