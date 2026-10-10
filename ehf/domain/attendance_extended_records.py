from __future__ import annotations

from dataclasses import dataclass

from ehf.domain.attendance_analytics import AttendanceRecord

EXTENDED_RECORD_LIMIT = 30
FINALS_PATTERN = "%final%"


@dataclass(frozen=True)
class ExtendedRecords:
    seasons: tuple[AttendanceRecord, ...] = ()
    clubs: tuple[AttendanceRecord, ...] = ()
    venues: tuple[AttendanceRecord, ...] = ()
    finals: tuple[AttendanceRecord, ...] = ()
    rivalries: tuple[AttendanceRecord, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (self.seasons or self.clubs or self.venues or self.finals or self.rivalries)
