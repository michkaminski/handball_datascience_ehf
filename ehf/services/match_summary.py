from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from ehf.domain.match_summary import (
    Baseline,
    MatchSummary,
    SummaryHeader,
    TickerAction,
    baseline,
    build_summary,
    match_events,
)

# Below this many matches in the season so far, the previous season joins the average.
MIN_REFERENCE_MATCHES = 30


class NoPlayByPlay(Exception):
    def __init__(self, match_id: int) -> None:
        super().__init__(f"Match {match_id} has no play-by-play")
        self.match_id = match_id


class MatchSummaryReader(Protocol):
    def header(self, match_id: int) -> SummaryHeader: ...

    def actions(self, match_ids: Sequence[int]) -> dict[int, tuple[TickerAction, ...]]: ...

    def reference_matches(self, competition_id: int, year: int) -> dict[int, list[int]]: ...


class MatchSummaryService:
    def __init__(self, reader: MatchSummaryReader) -> None:
        self._reader = reader
        self._baselines: dict[tuple[int, ...], Baseline] = {}

    def build(self, match_id: int, with_baseline: bool = True) -> MatchSummary:
        header = self._reader.header(match_id)
        actions = self._reader.actions([match_id]).get(match_id)
        if not actions:
            raise NoPlayByPlay(match_id)
        return build_summary(header, actions, self._baseline(header) if with_baseline else None)

    def _baseline(self, header: SummaryHeader) -> Baseline | None:
        seasons = self._reader.reference_matches(header.competition_id, header.year_start)
        ids = list(seasons.get(header.year_start, []))
        years = [header.year_start]
        if len(ids) < MIN_REFERENCE_MATCHES and seasons.get(header.year_start - 1):
            ids += seasons[header.year_start - 1]
            years.insert(0, header.year_start - 1)
        if not ids:
            return None
        key = tuple(ids)
        if key not in self._baselines:
            feeds = self._reader.actions(ids)
            label = f"{header.competition_name.removeprefix('EHF ')} {_seasons(years)}"
            self._baselines[key] = baseline(label, [match_events(feed) for feed in feeds.values()])
        return self._baselines[key]


def _seasons(years: list[int]) -> str:
    first, last = years[0], years[-1]
    return f"{first}-{str(last + 1)[-2:]}" if first == last else f"{first}–{str(last + 1)[-2:]}"
