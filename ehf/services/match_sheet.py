from __future__ import annotations

from datetime import date
from typing import Protocol

from ehf.domain.live_protocol import LiveProtocol, build_live_protocol

from ehf.domain.match_sheet import (
    MatchSheet,
    MatchSheetData,
    MatchSheetOptions,
    MatchSheetRequest,
    build_match_sheet,
)


class MatchSheetReader(Protocol):
    def options(self, season_id: int | None, competition_id: int | None) -> MatchSheetOptions: ...

    def fetch(self, request: MatchSheetRequest) -> MatchSheetData: ...


class MatchSheetService:
    def __init__(self, reader: MatchSheetReader) -> None:
        self._reader = reader

    def options(self, request: MatchSheetRequest) -> MatchSheetOptions:
        return self._reader.options(request.season_id, request.competition_id)

    def build(self, request: MatchSheetRequest) -> MatchSheet:
        return build_match_sheet(self._fetch(request), request)

    def live_protocol(self, request: MatchSheetRequest) -> LiveProtocol:
        return build_live_protocol(self._fetch(request), request, date.today())

    def _fetch(self, request: MatchSheetRequest) -> MatchSheetData:
        if not request.is_complete:
            raise ValueError("Choose a season and both teams")
        if request.home_id == request.away_id:
            raise ValueError("Home and away team must be different")
        return self._reader.fetch(request)
