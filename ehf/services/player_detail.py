from __future__ import annotations

from typing import Protocol

from ehf.domain.players import (
    PlayerCard,
    PlayerMatchFilterOptions,
    PlayerMatchFilters,
    PlayerMatchPage,
    PlayerProfile,
    PlayerSeasonRow,
)


class PlayerDetailReader(Protocol):
    def fetch_profile(self, player_id: int) -> PlayerProfile: ...

    def fetch_seasons(self, player_id: int) -> tuple[PlayerSeasonRow, ...]: ...

    def fetch_matches(self, player_id: int, filters: PlayerMatchFilters) -> PlayerMatchPage: ...

    def fetch_match_options(self, player_id: int) -> PlayerMatchFilterOptions: ...


class PlayerDetailService:
    def __init__(self, reader: PlayerDetailReader) -> None:
        self._reader = reader

    def get_card(self, player_id: int, match_filters: PlayerMatchFilters) -> PlayerCard:
        return PlayerCard(
            profile=self._reader.fetch_profile(player_id),
            seasons=self._reader.fetch_seasons(player_id),
            matches=self._reader.fetch_matches(player_id, match_filters),
            match_options=self._reader.fetch_match_options(player_id),
        )
