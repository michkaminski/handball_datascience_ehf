from __future__ import annotations

from typing import Protocol

from ehf.domain.referee_stats import build_referee_stats
from ehf.domain.referees import (
    RefereeCard,
    RefereeMatchFact,
    RefereeMatchFilterOptions,
    RefereeMatchFilters,
    RefereeMatchPage,
    RefereeProfile,
)


class RefereeDetailReader(Protocol):
    def fetch_profile(self, referee_id: int) -> RefereeProfile: ...

    def fetch_matches(self, referee_id: int, filters: RefereeMatchFilters) -> RefereeMatchPage: ...

    def fetch_match_options(self, referee_id: int) -> RefereeMatchFilterOptions: ...

    def fetch_facts(self, referee_id: int) -> tuple[RefereeMatchFact, ...]: ...


class RefereeDetailService:
    def __init__(self, reader: RefereeDetailReader) -> None:
        self._reader = reader

    def get_card(
        self,
        referee_id: int,
        match_filters: RefereeMatchFilters,
        expanded: frozenset[str],
    ) -> RefereeCard:
        return RefereeCard(
            profile=self._reader.fetch_profile(referee_id),
            matches=self._reader.fetch_matches(referee_id, match_filters),
            match_options=self._reader.fetch_match_options(referee_id),
            stats=build_referee_stats(self._reader.fetch_facts(referee_id), expanded),
        )
