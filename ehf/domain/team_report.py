from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

from ehf.domain.lineup_order import LineRole, line_role
from ehf.domain.match_detail import format_percentage, ratio_percentage
from ehf.domain.matches import Choice
from ehf.domain.team_detail import (
    SaveLine,
    TeamGoalkeeping,
    TeamMatch,
    TeamPlayerRow,
    TeamProfile,
    TeamRecord,
    TeamSeasonRow,
    TeamSeasonSheet,
)

MISSING = "—"
DEFAULT_LAST_MATCHES = 15
TOP_GOALS = 3
TOP_SHOOTERS = 3
MIN_SHOTS = 20
MIN_SHOTS_FACED = 50


def _percent(made: int | None, attempts: int | None) -> str:
    return format_percentage(round(ratio_percentage(made, attempts) or 0)) if attempts else MISSING


def short_competition(name: str) -> str:
    """'EHF Champions League Men' → 'Champions League'."""
    text = name.removeprefix("EHF ").strip()
    for suffix in (" Men", " Women"):
        text = text.removesuffix(suffix)
    return text


def _shirt_key(number: str | None) -> tuple[int, int, str]:
    text = (number or "").strip()
    if not text:
        return (2, 0, "")
    return (0, int(text), text) if text.isdigit() else (1, 0, text)


def _places(values: dict[str, float]) -> dict[str, int]:
    """Competition ranking: 1, 1, 3 …"""
    return {key: 1 + sum(1 for other in values.values() if other > value) for key, value in values.items()}


@dataclass(frozen=True)
class TeamReportRequest:
    club_id: int | None = None
    season_id: int | None = None
    last_matches: int = DEFAULT_LAST_MATCHES

    def __post_init__(self) -> None:
        if not 1 <= self.last_matches <= 40:
            raise ValueError("last_matches must be between 1 and 40")


@dataclass(frozen=True)
class TeamReportOptions:
    seasons: tuple[Choice, ...]
    teams: tuple[Choice, ...]


@dataclass(frozen=True)
class PreviousStint:
    """What a player did in the previous season for one club in one competition."""

    person_id: int
    club_id: int | None
    club_name: str
    competition_name: str
    matches: int
    goals: int | None
    shots: int | None
    saves: int | None
    shots_faced: int | None


@dataclass(frozen=True)
class MatchTeamStats:
    match_id: int
    shots: int | None
    penalty_goals: int | None
    penalty_shots: int | None
    two_min: int | None
    opponent_shots: int | None


# --- players -----------------------------------------------------------------


@dataclass(frozen=True)
class PreviousSeason:
    stints: tuple[PreviousStint, ...]
    club_id: int
    competitions: tuple[str, ...] = ()

    @property
    def played(self) -> bool:
        return bool(self.stints)

    @property
    def matches(self) -> int:
        return sum(stint.matches for stint in self.stints)

    @property
    def goals(self) -> int | None:
        known = [stint.goals for stint in self.stints if stint.goals is not None]
        return sum(known) if known else None

    @property
    def average_text(self) -> str:
        return f"{self.goals / self.matches:.1f}" if self.matches and self.goals is not None else MISSING

    @property
    def save_text(self) -> str:
        faced = sum(stint.shots_faced or 0 for stint in self.stints)
        return _percent(sum(stint.saves or 0 for stint in self.stints), faced) if faced else ""

    @property
    def same_club(self) -> bool:
        return any(stint.club_id == self.club_id for stint in self.stints)

    @property
    def where(self) -> str:
        """'same club' when nothing changed; otherwise the club and/or the competition."""
        parts = []
        for stint in self.stints:
            same_club = stint.club_id == self.club_id
            same_competition = stint.competition_name in self.competitions
            if same_club and same_competition:
                parts.append("same club")
            elif same_club:
                parts.append(f"same club · {short_competition(stint.competition_name)}")
            else:
                parts.append(f"{stint.club_name} · {short_competition(stint.competition_name)}")
        return "; ".join(dict.fromkeys(parts))


@dataclass(frozen=True)
class ReportPlayer:
    row: TeamPlayerRow
    role: LineRole
    previous: PreviousSeason
    top_goals: bool = False
    top_shooter: bool = False
    top_keeper: bool = False
    top_previous: bool = False
    new_group: bool = False
    nationalities: tuple[str, ...] = ()

    @property
    def nationality_text(self) -> str:
        return "/".join(self.nationalities)

    @property
    def number(self) -> str:
        return ", ".join(self.row.numbers)

    @property
    def average_text(self) -> str:
        r = self.row
        return f"{r.goals / r.matches:.1f}" if r.goals is not None and r.matches else MISSING

    @property
    def birth_year_text(self) -> str:
        return str(self.row.birth_year) if self.row.birth_year else ""

    @property
    def is_goalkeeper(self) -> bool:
        return self.role is LineRole.GOALKEEPER

    @property
    def shot_text(self) -> str:
        return _percent(self.row.goals, self.row.shots) if self.row.shots else MISSING

    @property
    def save_text(self) -> str:
        return _percent(self.row.saves, self.row.shots_faced) if self.row.shots_faced else ""

    @property
    def saves_detail(self) -> str:
        return f"{self.row.saves}/{self.row.shots_faced}" if self.row.shots_faced else ""


def report_players(
    rows: Sequence[TeamPlayerRow],
    stints: Sequence[PreviousStint],
    club_id: int,
    competitions: Sequence[str] = (),
    nationalities: dict[int, tuple[str, ...]] | None = None,
) -> tuple[ReportPlayer, ...]:
    by_person: dict[int, list[PreviousStint]] = {}
    for stint in stints:
        by_person.setdefault(stint.person_id, []).append(stint)

    def role(row: TeamPlayerRow) -> LineRole:
        return line_role(row.position, row.is_goalkeeper and not (row.position or "").strip())

    def key(row: TeamPlayerRow) -> str:
        return f"p{row.person_id}" if row.person_id is not None else f"n{row.name}"

    ordered = sorted(
        rows,
        key=lambda row: (role(row), _shirt_key(row.numbers[0] if row.numbers else None), row.name.casefold()),
    )
    goals = _places({key(row): row.goals for row in ordered if row.goals})
    shooters = _places(
        {key(row): row.goals / row.shots for row in ordered if row.shots and row.shots >= MIN_SHOTS and row.goals}
    )
    keepers = {
        key(row): row.saves / row.shots_faced
        for row in ordered
        if row.shots_faced and row.shots_faced >= MIN_SHOTS_FACED and row.saves is not None
    }
    best_keeper = max(keepers, key=keepers.get, default=None)
    previous = {
        key(row): PreviousSeason(tuple(by_person.get(row.person_id, ())), club_id, tuple(competitions))
        for row in ordered
    }
    previous_goals = _places({name: p.goals for name, p in previous.items() if p.goals})

    players = []
    for index, row in enumerate(ordered):
        current_role = role(row)
        players.append(
            ReportPlayer(
                row=row,
                role=current_role,
                previous=previous[key(row)],
                top_goals=goals.get(key(row), 99) <= TOP_GOALS,
                top_shooter=shooters.get(key(row), 99) <= TOP_SHOOTERS,
                top_keeper=key(row) == best_keeper,
                top_previous=previous_goals.get(key(row), 99) <= TOP_GOALS,
                new_group=index > 0 and current_role != role(ordered[index - 1]),
                nationalities=(nationalities or {}).get(row.person_id, ()) if row.person_id else (),
            )
        )
    return tuple(players)


# --- last matches ------------------------------------------------------------


@dataclass(frozen=True)
class ReportMatch:
    match: TeamMatch
    stats: MatchTeamStats | None
    scorers: tuple[tuple[str, int], ...]
    own_saves: SaveLine | None
    opponent_saves: SaveLine | None

    @property
    def scorers_text(self) -> str:
        return ", ".join(f"{name} {goals}" for name, goals in self.scorers) or MISSING

    @property
    def shots_text(self) -> str:
        if self.stats is None or self.stats.shots is None:
            return MISSING
        return f"{self.match.goals_for if self.match.goals_for is not None else '?'}/{self.stats.shots}"

    @property
    def penalties_text(self) -> str:
        if self.stats is None or self.stats.penalty_shots is None:
            return MISSING
        return f"{self.stats.penalty_goals or 0}/{self.stats.penalty_shots}"

    @property
    def two_min_text(self) -> str:
        if self.stats is None or self.stats.two_min is None:
            return MISSING
        return str(self.stats.two_min)


def short_name(name: str) -> str:
    """'Ómar Ingi Magnusson' → 'Ó. Magnusson' (the initial tells apart brothers and namesakes)."""
    parts = name.split()
    if len(parts) < 2:
        return name
    return f"{parts[0][0]}. {parts[-1]}"


# --- the report --------------------------------------------------------------


@dataclass(frozen=True)
class TeamReport:
    profile: TeamProfile
    season_code: str
    previous_season_code: str | None
    competitions: tuple[str, ...]
    record: TeamRecord
    goalkeeping: TeamGoalkeeping
    seasons: tuple[TeamSeasonRow, ...]
    players: tuple[ReportPlayer, ...]
    last_matches: tuple[ReportMatch, ...]
    generated: date

    @property
    def keepers(self) -> tuple[ReportPlayer, ...]:
        return tuple(player for player in self.players if player.is_goalkeeper)

    @property
    def top_scorer(self) -> ReportPlayer | None:
        scored = [player for player in self.players if player.row.goals]
        return max(scored, key=lambda player: player.row.goals, default=None)

    @property
    def last_form(self) -> str:
        return " ".join(item.match.outcome or "·" for item in reversed(self.last_matches[:5]))

    @property
    def generated_text(self) -> str:
        return self.generated.strftime("%d.%m.%Y")


@dataclass(frozen=True)
class SeasonSheetPage:
    season_code: str
    competitions: tuple[str, ...]
    record: TeamRecord | None
    sheet: TeamSeasonSheet | None
    best: tuple[int | None, ...]


@dataclass(frozen=True)
class SeasonSheets:
    """Season sheets of one team: the chosen season and the one before it."""

    profile: TeamProfile
    pages: tuple[SeasonSheetPage, ...]
    generated: date

    @property
    def generated_text(self) -> str:
        return self.generated.strftime("%d.%m.%Y")


def sheet_best_per_match(sheet: TeamSeasonSheet) -> tuple[int | None, ...]:
    """Most goals by one player in each sheet column (to mark the match's top scorer)."""
    best = []
    for index in range(len(sheet.matches)):
        goals = [row.cells[index].goals for row in sheet.rows if row.cells[index] and row.cells[index].goals]
        best.append(max(goals) if goals else None)
    return tuple(best)


def match_date_key(match: TeamMatch) -> datetime:
    return match.kickoff_at.replace(tzinfo=None) if match.kickoff_at else datetime.min
