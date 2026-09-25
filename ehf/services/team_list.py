from __future__ import annotations

from typing import Protocol

from ehf.domain.gender import GENDER_CHOICES
from ehf.domain.matches import Choice
from ehf.domain.teams import TeamFilterOptions, TeamFilters, TeamListPage


class TeamListReader(Protocol):
    def fetch_page(self, filters: TeamFilters) -> TeamListPage: ...

    def fetch_seasons(self) -> tuple[Choice, ...]: ...


class TeamListService:
    def __init__(self, reader: TeamListReader) -> None:
        self._reader = reader

    def list_teams(self, filters: TeamFilters) -> TeamListPage:
        return self._reader.fetch_page(filters)

    def filter_options(self) -> TeamFilterOptions:
        return TeamFilterOptions(seasons=self._reader.fetch_seasons(), genders=GENDER_CHOICES)
