from __future__ import annotations

from collections.abc import Sequence
from statistics import mean
from typing import Protocol

from ehf.domain.news import (
    NewsCompetition,
    NewsGoalkeeper,
    NewsMatchRecord,
    NewsPage,
    NewsPerformanceWithCompetition,
    NewsResultMatch,
    NewsScorer,
    NewsSection,
    NewsSeason,
)
from ehf.infrastructure.news_reader import (
    BEST_PERFORMANCES_LIMIT,
    GOALKEEPERS_PER_COMPETITION,
    MATCHES_PER_SECTION,
    SCORERS_PER_COMPETITION,
)


class NewsReader(Protocol):
    def fetch_current_season(self) -> NewsSeason | None: ...

    def fetch_competitions(self, season_id: int) -> tuple[NewsCompetition, ...]: ...

    def fetch_played_matches(self, season_id: int) -> tuple[NewsResultMatch, ...]: ...

    def fetch_top_scorers(
        self, season_id: int, limit: int = SCORERS_PER_COMPETITION
    ) -> tuple[NewsScorer, ...]: ...

    def fetch_top_goalkeepers(
        self, season_id: int, limit: int = GOALKEEPERS_PER_COMPETITION
    ) -> tuple[NewsGoalkeeper, ...]: ...

    def fetch_best_performances(
        self, season_id: int, limit: int = BEST_PERFORMANCES_LIMIT
    ) -> tuple: ...

    def fetch_upcoming_sections(self, season_id: int | None = None, limit: int = 6): ...


class NewsService:
    def __init__(self, reader: NewsReader) -> None:
        self._reader = reader

    def load_page(self) -> NewsPage:
        season = self._reader.fetch_current_season()
        upcoming_sections = self._reader.fetch_upcoming_sections(
            season.id if season else None
        )
        if season is None:
            return NewsPage(
                season=None,
                sections=(),
                upcoming_sections=upcoming_sections,
                played_count=0,
                total_goals=0,
                last_kickoff=None,
                most_goals_match=None,
                biggest_win=None,
                best_performances=(),
                highest_scoring_section=None,
            )
        competitions_list = self._reader.fetch_competitions(season.id)
        competitions = {competition.id: competition for competition in competitions_list}
        matches = [
            match
            for match in self._reader.fetch_played_matches(season.id)
            if match.competition_id in competitions
        ]
        scorers = self._reader.fetch_top_scorers(season.id)
        goalkeepers = self._reader.fetch_top_goalkeepers(season.id)
        performances = self._reader.fetch_best_performances(season.id)
        sections = tuple(
            self._section(
                competition,
                [match for match in matches if match.competition_id == competition.id],
                tuple(scorer for scorer in scorers if scorer.competition_id == competition.id),
                tuple(
                    keeper
                    for keeper in goalkeepers
                    if keeper.competition_id == competition.id
                ),
            )
            for competition in sorted(competitions_list, key=lambda item: item.sort_rank)
        )
        return NewsPage(
            season=season,
            sections=sections,
            upcoming_sections=upcoming_sections,
            played_count=len(matches),
            total_goals=sum(match.total_goals for match in matches),
            last_kickoff=max((match.kickoff_at for match in matches if match.kickoff_at), default=None),
            most_goals_match=self._record(matches, competitions, lambda match: match.total_goals),
            biggest_win=self._record(matches, competitions, lambda match: match.goal_difference),
            best_performances=tuple(
                NewsPerformanceWithCompetition(performance, competitions[performance.competition_id])
                for performance in performances
                if performance.competition_id in competitions
            ),
            highest_scoring_section=max(
                (section for section in sections if section.average_goals is not None),
                key=lambda section: section.average_goals or 0.0,
                default=None,
            ),
        )

    @staticmethod
    def _section(
        competition: NewsCompetition,
        matches: Sequence[NewsResultMatch],
        scorers: tuple[NewsScorer, ...],
        goalkeepers: tuple[NewsGoalkeeper, ...],
    ) -> NewsSection:
        return NewsSection(
            competition=competition,
            played_count=len(matches),
            average_goals=mean(match.total_goals for match in matches) if matches else None,
            recent_matches=tuple(matches[:MATCHES_PER_SECTION]),
            scorers=scorers,
            goalkeepers=goalkeepers,
        )

    @staticmethod
    def _record(
        matches: Sequence[NewsResultMatch],
        competitions: dict[int, NewsCompetition],
        measure,
    ) -> NewsMatchRecord | None:
        if not matches:
            return None
        best = max(matches, key=measure)
        value = measure(best)
        if value <= 0:
            return None
        return NewsMatchRecord(best, competitions[best.competition_id], value)
