from __future__ import annotations

from typing import Protocol

from ehf.domain.venue_stats import build_venue_stats
from ehf.domain.venues import (
    VenueCard,
    VenueMatchFact,
    VenueMatchFilterOptions,
    VenueMatchFilters,
    VenueMatchPage,
    VenuePlayerFilters,
    VenuePlayerItem,
    VenuePlayerPage,
    VenueProfile,
)


class VenueDetailReader(Protocol):
    def fetch_profile(self, venue_id: int) -> VenueProfile: ...

    def fetch_matches(self, venue_id: int, filters: VenueMatchFilters) -> VenueMatchPage: ...

    def fetch_match_options(self, venue_id: int) -> VenueMatchFilterOptions: ...

    def fetch_players(self, venue_id: int, filters: VenuePlayerFilters) -> VenuePlayerPage: ...

    def fetch_player_ranks(self, venue_id: int) -> tuple[VenuePlayerItem, ...]: ...

    def fetch_facts(self, venue_id: int) -> tuple[VenueMatchFact, ...]: ...


class VenueDetailService:
    def __init__(self, reader: VenueDetailReader) -> None:
        self._reader = reader

    def get_card(
        self,
        venue_id: int,
        match_filters: VenueMatchFilters,
        player_filters: VenuePlayerFilters,
        expanded: frozenset[str],
    ) -> VenueCard:
        return VenueCard(
            profile=self._reader.fetch_profile(venue_id),
            matches=self._reader.fetch_matches(venue_id, match_filters),
            match_options=self._reader.fetch_match_options(venue_id),
            players=self._reader.fetch_players(venue_id, player_filters),
            stats=build_venue_stats(
                self._reader.fetch_facts(venue_id),
                self._reader.fetch_player_ranks(venue_id),
                expanded,
            ),
        )
