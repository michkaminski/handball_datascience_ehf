from __future__ import annotations

from typing import Protocol

from ehf.domain.lineup_order import with_sorted_lineups
from ehf.domain.match_detail import MatchDetail


class MatchDetailReader(Protocol):
    def fetch(self, match_id: int) -> MatchDetail: ...


class MatchDetailService:
    def __init__(self, reader: MatchDetailReader) -> None:
        self._reader = reader

    def get_match(self, match_id: int) -> MatchDetail:
        return with_sorted_lineups(self._reader.fetch(match_id).with_top_scorers())
