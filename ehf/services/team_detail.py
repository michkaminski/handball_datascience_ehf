from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from ehf.domain.matches import Choice
from ehf.domain.team_detail import (
    TeamCard,
    TeamCardData,
    TeamDetailFilters,
    TeamFilterOptions,
    TeamSheetFilters,
    filter_matches,
    name_history,
    player_rows,
    season_rows,
    season_sheet,
    team_attendance,
    team_goalkeeping,
    team_record,
    without_missing_saves,
)


class TeamDetailReader(Protocol):
    def fetch(self, club_id: int) -> TeamCardData: ...


class TeamDetailService:
    def __init__(self, reader: TeamDetailReader) -> None:
        self._reader = reader

    def get_card(self, club_id: int, filters: TeamDetailFilters, sheet_filters: TeamSheetFilters) -> TeamCard:
        data = self._reader.fetch(club_id)
        entries, missing_saves = without_missing_saves(data.entries)
        matches = filter_matches(data.matches, filters)
        if sheet_filters.season_id is None and data.editions:
            sheet_filters = replace(sheet_filters, season_id=data.editions[0].season_id)
        sheet_matches = filter_matches(
            data.matches,
            TeamDetailFilters(
                season_id=sheet_filters.season_id,
                competition_id=sheet_filters.competition_id,
                opponent=sheet_filters.opponent,
            ),
        )
        sheet_season = next(
            (e.season_code for e in data.editions if e.season_id == sheet_filters.season_id), None
        )
        return TeamCard(
            profile=data.profile,
            editions=data.editions,
            names=name_history(data.editions),
            venues=data.venues,
            all_matches=data.matches,
            attendance=team_attendance(data.matches),
            seasons=season_rows(data.matches, data.editions),
            options=self._options(data),
            filters=filters,
            matches=matches,
            match_attendance=team_attendance(matches),
            match_record=team_record(matches),
            players=player_rows(entries, matches, filters.player),
            goalkeeping=replace(
                team_goalkeeping(entries, matches),
                missing_matches=sum(match.match_id in missing_saves for match in matches),
            ),
            sheet_filters=sheet_filters,
            sheet=season_sheet(entries, sheet_matches, sheet_season),
        )

    @staticmethod
    def _options(data: TeamCardData) -> TeamFilterOptions:
        seasons = dict.fromkeys((e.season_id, e.season_code) for e in data.editions)
        competitions = dict.fromkeys(
            (e.competition_id, e.competition_name) for e in sorted(data.editions, key=lambda e: e.competition_name)
        )
        return TeamFilterOptions(
            seasons=tuple(Choice(str(value), label) for value, label in seasons),
            competitions=tuple(Choice(str(value), label) for value, label in competitions),
        )
