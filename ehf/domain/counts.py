from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NamedCount:
    key: str
    label: str
    value: int
    detail: str | None = None


@dataclass(frozen=True)
class CountSeries:
    items: tuple[NamedCount, ...]

    @property
    def maximum(self) -> int:
        return max((item.value for item in self.items), default=0)

    def width(self, item: NamedCount) -> int:
        return 0 if self.maximum <= 0 else round(100 * item.value / self.maximum)

    def visible(self, expanded: bool, limit: int = 10) -> tuple[NamedCount, ...]:
        return self.items if expanded or len(self.items) <= limit else self.items[:limit]


@dataclass(frozen=True)
class HeatCell:
    season: str
    month: int
    value: int
    level: int


@dataclass(frozen=True)
class Heatmap:
    seasons: tuple[str, ...]
    cells: tuple[HeatCell, ...]

    def cell(self, season: str, month: int) -> HeatCell | None:
        for item in self.cells:
            if item.season == season and item.month == month:
                return item
        return None


@dataclass(frozen=True)
class MatchRecord:
    label: str
    match_id: int | None
    text: str


def median(values: tuple[int, ...]) -> float | None:
    if not values:
        return None
    ordered = tuple(sorted(values))
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2


def mean(values: tuple[int, ...]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def completeness(known: int, total: int) -> float | None:
    if total <= 0:
        return None
    return known * 100 / total


def heat_level(value: int, maximum: int) -> int:
    if value <= 0 or maximum <= 0:
        return 0
    return min(4, max(1, round(4 * value / maximum)))


WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
