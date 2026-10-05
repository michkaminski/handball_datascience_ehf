from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import date
from typing import Protocol

from ehf.domain.team_detail import (
    TeamCardData,
    TeamDetailFilters,
    filter_matches,
    player_rows,
    season_rows,
    season_sheet,
    team_goalkeeping,
    team_record,
    without_missing_saves,
)
from ehf.domain.team_report import (
    MatchTeamStats,
    PreviousStint,
    ReportMatch,
    SeasonSheetPage,
    SeasonSheets,
    TeamReport,
    TeamReportOptions,
    TeamReportRequest,
    match_date_key,
    report_players,
    sheet_best_per_match,
    short_name,
)

SCORERS_PER_MATCH = 3


class TeamCardReader(Protocol):
    def fetch(self, club_id: int) -> TeamCardData: ...


class TeamReportReader(Protocol):
    def options(self, season_id: int | None) -> TeamReportOptions: ...

    def season_info(self, season_id: int) -> tuple[str, int | None, str | None]: ...

    def previous_stints(self, people: Sequence[int], season_id: int) -> tuple[PreviousStint, ...]: ...

    def nationalities(self, people: Sequence[int]) -> dict[int, tuple[str, ...]]: ...

    def match_stats(self, club_id: int, matches: Sequence[int]) -> dict[int, MatchTeamStats]: ...


class TeamReportService:
    def __init__(self, teams: TeamCardReader, reports: TeamReportReader) -> None:
        self._teams = teams
        self._reports = reports

    def options(self, season_id: int | None) -> TeamReportOptions:
        return self._reports.options(season_id)

    def build(self, request: TeamReportRequest, today: date | None = None) -> TeamReport:
        if request.club_id is None or request.season_id is None:
            raise ValueError("Choose a season and a team")
        data = self._teams.fetch(request.club_id)
        season_code, previous_id, previous_code = self._reports.season_info(request.season_id)
        editions = [edition for edition in data.editions if edition.season_id == request.season_id]
        if not editions:
            raise ValueError(f"{data.profile.name} did not play in season {season_code}")
        year = editions[0].year_start

        entries, _ = without_missing_saves(data.entries)
        season_matches = filter_matches(data.matches, TeamDetailFilters(season_id=request.season_id))
        players = player_rows(entries, season_matches)
        people = [row.person_id for row in players if row.person_id is not None]
        stints = self._reports.previous_stints(people, previous_id) if previous_id else ()
        competitions = tuple(dict.fromkeys(edition.competition_name for edition in editions))

        history = [match for match in data.matches if match.year_start <= year]
        last = sorted(
            (match for match in history if match.is_finished),
            key=match_date_key,
            reverse=True,
        )[: request.last_matches]
        keeping = team_goalkeeping(entries, last).by_match_id
        stats = self._reports.match_stats(request.club_id, [match.match_id for match in last])

        return TeamReport(
            profile=data.profile,
            season_code=season_code,
            previous_season_code=previous_code,
            competitions=competitions,
            record=team_record(season_matches),
            goalkeeping=team_goalkeeping(entries, season_matches),
            seasons=season_rows(history, [e for e in data.editions if e.year_start <= year]),
            players=report_players(
                players, stints, request.club_id, competitions, self._reports.nationalities(people)
            ),
            last_matches=tuple(
                ReportMatch(
                    match=match,
                    stats=stats.get(match.match_id),
                    scorers=self._scorers(entries, match.match_id),
                    own_saves=keeping[match.match_id].own if match.match_id in keeping else None,
                    opponent_saves=keeping[match.match_id].opponents if match.match_id in keeping else None,
                )
                for match in last
            ),
            generated=today or date.today(),
        )

    def season_sheets(self, request: TeamReportRequest, today: date | None = None) -> SeasonSheets:
        """The chosen season's sheet and the previous season's (empty page when the team did not play)."""
        if request.club_id is None or request.season_id is None:
            raise ValueError("Choose a season and a team")
        data = self._teams.fetch(request.club_id)
        season_code, previous_id, previous_code = self._reports.season_info(request.season_id)
        if not any(edition.season_id == request.season_id for edition in data.editions):
            raise ValueError(f"{data.profile.name} did not play in season {season_code}")
        entries, _ = without_missing_saves(data.entries)
        pages = [self._sheet_page(data, entries, request.season_id, season_code)]
        if previous_id is not None and previous_code is not None:
            pages.append(self._sheet_page(data, entries, previous_id, previous_code))
        people = sorted(
            {row.person_id for page in pages if page.sheet for row in page.sheet.rows if row.person_id is not None}
        )
        nationalities = self._reports.nationalities(people)
        pages = [replace(page, nationalities=nationalities) for page in pages]
        return SeasonSheets(profile=data.profile, pages=tuple(pages), generated=today or date.today())

    @staticmethod
    def _sheet_page(data: TeamCardData, entries, season_id: int, season_code: str) -> SeasonSheetPage:
        editions = [edition for edition in data.editions if edition.season_id == season_id]
        if not editions:
            return SeasonSheetPage(season_code, (), None, None, ())
        matches = filter_matches(data.matches, TeamDetailFilters(season_id=season_id))
        sheet = season_sheet(entries, matches, season_code)
        return SeasonSheetPage(
            season_code=season_code,
            competitions=tuple(dict.fromkeys(edition.competition_name for edition in editions)),
            record=team_record(matches),
            sheet=sheet,
            best=sheet_best_per_match(sheet),
        )

    @staticmethod
    def _scorers(entries, match_id: int) -> tuple[tuple[str, int], ...]:
        scored = [e for e in entries if e.own and e.match_id == match_id and e.goals]
        scored.sort(key=lambda e: -e.goals)
        return tuple((short_name(e.name), e.goals) for e in scored[:SCORERS_PER_MATCH])
