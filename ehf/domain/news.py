from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ehf.domain.matches import MatchListItem, format_score

COMPETITION_SORT_KEYS: tuple[str, ...] = (
    "ehfcl-men",
    "ehfcl-women",
    "ehfel-men",
    "ehfel-women",
    "ehfec-men",
    "ehfec-women",
)


@dataclass(frozen=True)
class NewsSeason:
    id: int
    code: str


@dataclass(frozen=True)
class NewsCompetition:
    id: int
    key: str
    name: str

    @property
    def sort_rank(self) -> tuple[int, str]:
        if self.key in COMPETITION_SORT_KEYS:
            return (COMPETITION_SORT_KEYS.index(self.key), self.name)
        return (len(COMPETITION_SORT_KEYS), self.name)


@dataclass(frozen=True)
class NewsResultMatch:
    id: int
    kickoff_at: datetime | None
    competition_id: int
    home_name: str | None
    away_name: str | None
    score_home: int | None
    score_away: int | None
    result_type: str | None

    @property
    def total_goals(self) -> int:
        return (self.score_home or 0) + (self.score_away or 0)

    @property
    def goal_difference(self) -> int:
        return abs((self.score_home or 0) - (self.score_away or 0))

    @property
    def score_text(self) -> str:
        return format_score(self.score_home, self.score_away, self.result_type)


@dataclass(frozen=True)
class NewsScorer:
    competition_id: int
    player_id: int
    player_name: str
    team: str | None
    matches: int
    goals: int


@dataclass(frozen=True)
class NewsGoalkeeper:
    competition_id: int
    player_id: int
    player_name: str
    team: str | None
    matches: int
    shots_faced: int
    saves: int
    average_save_percentage: float


@dataclass(frozen=True)
class NewsPerformance:
    competition_id: int
    match_id: int
    kickoff_at: datetime | None
    player_id: int
    player_name: str
    team: str | None
    goals: int


@dataclass(frozen=True)
class NewsSection:
    competition: NewsCompetition
    played_count: int
    average_goals: float | None
    recent_matches: tuple[NewsResultMatch, ...]
    scorers: tuple[NewsScorer, ...]
    goalkeepers: tuple[NewsGoalkeeper, ...]


@dataclass(frozen=True)
class NewsMatchRecord:
    match: NewsResultMatch
    competition: NewsCompetition
    value: int


@dataclass(frozen=True)
class NewsPerformanceWithCompetition:
    performance: NewsPerformance
    competition: NewsCompetition


@dataclass(frozen=True)
class UpcomingSection:
    competition: NewsCompetition
    matches: tuple[MatchListItem, ...]


@dataclass(frozen=True)
class NewsPage:
    season: NewsSeason | None
    sections: tuple[NewsSection, ...]
    upcoming_sections: tuple[UpcomingSection, ...]
    played_count: int
    total_goals: int
    last_kickoff: datetime | None
    most_goals_match: NewsMatchRecord | None
    biggest_win: NewsMatchRecord | None
    best_performances: tuple[NewsPerformanceWithCompetition, ...]
    highest_scoring_section: NewsSection | None

    @staticmethod
    def empty() -> NewsPage:
        return NewsPage(
            season=None,
            sections=(),
            upcoming_sections=(),
            played_count=0,
            total_goals=0,
            last_kickoff=None,
            most_goals_match=None,
            biggest_win=None,
            best_performances=(),
            highest_scoring_section=None,
        )
