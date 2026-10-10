from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ehf.domain.attendance_analytics import format_rounded
from ehf.domain.goal_distribution import format_int

DIMENSION_MONTH = "month"
DIMENSION_WEEKDAY = "weekday"
DIMENSION_HOUR = "hour"
DIMENSION_DAY_TYPE = "day_type"
DIMENSION_PHASE = "phase"
DIMENSION_HEATMAP = "heatmap"

WEEKDAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MONTH_LABELS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)
DAY_TYPE_WEEKDAY = "weekday"
DAY_TYPE_WEEKEND = "weekend"
DAY_TYPE_LABELS = {DAY_TYPE_WEEKDAY: "Weekday (Mon–Fri)", DAY_TYPE_WEEKEND: "Weekend (Sat–Sun)"}
UNKNOWN_PHASE_LABEL = "Unknown phase"
CALENDAR_NOTE = (
    "Calendar views use matches with a known kickoff time; phase also covers matches without one. "
    "Means use known attendance only."
)


@dataclass(frozen=True)
class CalendarCell:
    dimension: str
    key: str
    secondary: str | None
    played: int
    known: int
    mean: float | None

    def __post_init__(self) -> None:
        if self.played < 0 or self.known < 0:
            raise ValueError("match counts cannot be negative")
        if self.known > self.played:
            raise ValueError("known matches cannot exceed played matches")


@dataclass(frozen=True)
class CalendarBucket:
    key: str
    label: str
    played: int
    known: int
    mean: float | None
    relative: float | None

    @property
    def mean_label(self) -> str:
        return format_rounded(self.mean)

    @property
    def played_label(self) -> str:
        return format_int(self.played)

    @property
    def known_label(self) -> str:
        return format_int(self.known)

    @property
    def bar_percent(self) -> int:
        if self.relative is None:
            return 0
        return round(self.relative * 100)


@dataclass(frozen=True)
class HeatmapCell:
    weekday: int
    hour: int
    played: int
    known: int
    mean: float | None


@dataclass(frozen=True)
class CalendarReport:
    months: tuple[CalendarBucket, ...]
    weekdays: tuple[CalendarBucket, ...]
    hours: tuple[CalendarBucket, ...]
    day_types: tuple[CalendarBucket, ...]
    phases: tuple[CalendarBucket, ...]
    heatmap: tuple[HeatmapCell, ...]

    @property
    def is_empty(self) -> bool:
        return not (self.months or self.weekdays or self.hours or self.day_types or self.phases)

    @property
    def has_heatmap(self) -> bool:
        return any(cell.mean is not None for cell in self.heatmap)


class CalendarCalculator:
    @staticmethod
    def build(cells: Sequence[CalendarCell]) -> CalendarReport:
        by_dimension: dict[str, list[CalendarCell]] = {}
        for cell in cells:
            by_dimension.setdefault(cell.dimension, []).append(cell)
        return CalendarReport(
            months=CalendarCalculator._ordered(
                by_dimension.get(DIMENSION_MONTH, ()),
                lambda key: int(key),
                lambda key: MONTH_LABELS[int(key) - 1],
                valid=lambda key: 1 <= int(key) <= 12,
            ),
            weekdays=CalendarCalculator._ordered(
                by_dimension.get(DIMENSION_WEEKDAY, ()),
                lambda key: int(key),
                lambda key: WEEKDAY_LABELS[int(key)],
                valid=lambda key: 0 <= int(key) <= 6,
            ),
            hours=CalendarCalculator._ordered(
                by_dimension.get(DIMENSION_HOUR, ()),
                lambda key: int(key),
                lambda key: f"{int(key):02d}:00",
                valid=lambda key: 0 <= int(key) <= 23,
            ),
            day_types=CalendarCalculator._ordered(
                by_dimension.get(DIMENSION_DAY_TYPE, ()),
                lambda key: 0 if key == DAY_TYPE_WEEKDAY else 1,
                lambda key: DAY_TYPE_LABELS[key],
                valid=lambda key: key in DAY_TYPE_LABELS,
            ),
            phases=CalendarCalculator._phases(by_dimension.get(DIMENSION_PHASE, ())),
            heatmap=CalendarCalculator._heatmap(by_dimension.get(DIMENSION_HEATMAP, ())),
        )

    @staticmethod
    def _ordered(cells, order, label, valid) -> tuple[CalendarBucket, ...]:
        usable = [cell for cell in cells if valid(cell.key)]
        usable.sort(key=lambda cell: order(cell.key))
        return CalendarCalculator._buckets(usable, label)

    @staticmethod
    def _phases(cells: Sequence[CalendarCell]) -> tuple[CalendarBucket, ...]:
        ordered = sorted(
            cells,
            key=lambda cell: (
                cell.mean is None,
                -(cell.mean or 0.0),
                -cell.known,
                cell.key.casefold(),
            ),
        )
        return CalendarCalculator._buckets(ordered, lambda key: key or UNKNOWN_PHASE_LABEL)

    @staticmethod
    def _buckets(cells: Sequence[CalendarCell], label) -> tuple[CalendarBucket, ...]:
        means = [cell.mean for cell in cells if cell.mean is not None]
        top = max(means) if means else None
        return tuple(
            CalendarBucket(
                key=cell.key,
                label=label(cell.key),
                played=cell.played,
                known=cell.known,
                mean=cell.mean,
                relative=(cell.mean / top) if cell.mean is not None and top else None,
            )
            for cell in cells
        )

    @staticmethod
    def _heatmap(cells: Sequence[CalendarCell]) -> tuple[HeatmapCell, ...]:
        result = [
            HeatmapCell(
                weekday=int(cell.key),
                hour=int(cell.secondary),
                played=cell.played,
                known=cell.known,
                mean=cell.mean,
            )
            for cell in cells
            if cell.secondary is not None
            and 0 <= int(cell.key) <= 6
            and 0 <= int(cell.secondary) <= 23
        ]
        result.sort(key=lambda cell: (cell.weekday, cell.hour))
        return tuple(result)
