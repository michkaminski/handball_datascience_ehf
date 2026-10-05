from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, time
from enum import Enum

from ehf.domain.lineup_order import LineRole, line_role
from ehf.domain.match_detail import format_percentage, ratio_percentage
from ehf.domain.matches import Choice

TOP_SCORERS = 4
FLOW_ROWS = 34
PLAYER_SPACE_MM = 173.0
ROW_BORDER_MM = 0.2
ROW_MIN_MM = 3.0
ROW_MAX_MM = 5.2
FONT_PER_MM = 1.6
FONT_MAX_PT = 8.5

POSITION_LETTERS = {
    LineRole.GOALKEEPER: "G",
    LineRole.BACKCOURT: "B",
    LineRole.WING: "W",
    LineRole.PIVOT: "P",
}


class SheetOrder(str, Enum):
    POSITIONS = "positions"
    NUMBERS = "numbers"


@dataclass(frozen=True)
class MatchSheetRequest:
    season_id: int | None = None
    competition_id: int | None = None
    home_id: int | None = None
    away_id: int | None = None
    match_date: date | None = None
    kickoff: time | None = None
    venue_id: int | None = None
    order: SheetOrder = SheetOrder.POSITIONS
    previous_season: bool = False

    @property
    def is_complete(self) -> bool:
        return self.season_id is not None and self.home_id is not None and self.away_id is not None


@dataclass(frozen=True)
class MatchSheetOptions:
    seasons: tuple[Choice, ...]
    competitions: tuple[Choice, ...]
    teams: tuple[Choice, ...]
    venues: tuple[Choice, ...]


# --- data read from the database ---------------------------------------------


@dataclass(frozen=True)
class SquadPlayer:
    """One player of a team in the chosen season (or the previous one, or the registered roster)."""

    person_id: int | None
    name: str
    first_name: str | None
    last_name: str | None
    number: str | None
    position: str | None
    is_goalkeeper: bool
    birth_year: int | None
    matches: int | None
    goals: int | None
    saves: int | None
    shots_faced: int | None

    @property
    def key(self) -> str:
        return f"p{self.person_id}" if self.person_id is not None else f"n{self.name.casefold()}"


@dataclass(frozen=True)
class SquadEntry:
    """One lineup row of the team, newest match first."""

    match_id: int
    person_id: int | None
    name: str
    first_name: str | None
    last_name: str | None
    number: str | None
    position: str | None
    is_goalkeeper: bool
    birth_year: int | None
    goals: int | None
    saves: int | None
    shots_faced: int | None


def aggregate_squad(entries: tuple[SquadEntry, ...], no_save_data: frozenset[int]) -> tuple[SquadPlayer, ...]:
    groups: dict[str, list[SquadEntry]] = {}
    for entry in entries:
        key = f"p{entry.person_id}" if entry.person_id is not None else f"n{entry.name.casefold()}"
        groups.setdefault(key, []).append(entry)
    players = []
    for group in groups.values():
        latest = group[0]
        keeping = [e for e in group if e.shots_faced and e.match_id not in no_save_data]
        goals = [e.goals for e in group if e.goals is not None]
        players.append(
            SquadPlayer(
                person_id=latest.person_id,
                name=latest.name,
                first_name=latest.first_name,
                last_name=latest.last_name,
                number=next((e.number for e in group if (e.number or "").strip()), None),
                position=next((e.position for e in group if (e.position or "").strip()), None),
                is_goalkeeper=any(e.is_goalkeeper or e.shots_faced for e in group),
                birth_year=latest.birth_year,
                matches=len({e.match_id for e in group}),
                goals=sum(goals) if goals else 0,
                saves=sum(e.saves or 0 for e in keeping) if keeping else None,
                shots_faced=sum(e.shots_faced or 0 for e in keeping) if keeping else None,
            )
        )
    return tuple(players)


@dataclass(frozen=True)
class SheetVenue:
    id: int
    name: str
    city: str | None
    country_code: str | None


@dataclass(frozen=True)
class SheetTeamData:
    club_id: int
    name: str
    country_code: str | None
    current: tuple[SquadPlayer, ...]
    previous: tuple[SquadPlayer, ...]
    roster: tuple[SquadPlayer, ...]


@dataclass(frozen=True)
class MatchSheetData:
    season_code: str
    competition_name: str | None
    home: SheetTeamData
    away: SheetTeamData
    venue: SheetVenue | None
    stats_until: date | None


# --- what the print shows ----------------------------------------------------


@dataclass(frozen=True)
class SheetPlayer:
    number: str
    name: str
    position: str
    birth_year: str
    matches: str
    goals: str
    average: str
    percentage: str
    highlight: bool
    new_group: bool


@dataclass(frozen=True)
class SheetTeam:
    letter: str
    name: str
    country_code: str | None
    source: str
    players: tuple[SheetPlayer, ...]

    @property
    def from_roster(self) -> bool:
        return self.source == "roster"


@dataclass(frozen=True)
class SheetLayout:
    row_mm: float
    font_pt: float
    flow_rows: int = FLOW_ROWS


@dataclass(frozen=True)
class MatchSheet:
    season_code: str
    competition_name: str | None
    home: SheetTeam
    away: SheetTeam
    venue: SheetVenue | None
    match_date: date | None
    kickoff: time | None
    stats_until: date | None
    layout: SheetLayout

    @property
    def teams(self) -> tuple[SheetTeam, SheetTeam]:
        return (self.home, self.away)

    @property
    def date_text(self) -> str:
        return self.match_date.strftime("%d.%m.%Y") if self.match_date else ""

    @property
    def time_text(self) -> str:
        return self.kickoff.strftime("%H:%M") if self.kickoff else ""

    @property
    def venue_text(self) -> str:
        if self.venue is None:
            return ""
        parts = [self.venue.name, self.venue.city, self.venue.country_code]
        return ", ".join(part for part in parts if part)


# --- rules -------------------------------------------------------------------


def _shirt_key(number: str | None) -> tuple[int, int, str]:
    text = (number or "").strip()
    if not text:
        return (2, 0, "")
    if text.isdigit():
        return (0, int(text), text)
    return (1, 0, text)


def _role(player: SquadPlayer) -> LineRole:
    return line_role(player.position, player.is_goalkeeper)


def _surname_key(player: SquadPlayer) -> tuple[str, str]:
    return ((player.last_name or player.name).casefold(), (player.first_name or "").casefold())


def order_players(players: tuple[SquadPlayer, ...], order: SheetOrder) -> tuple[SquadPlayer, ...]:
    """Positions: GK, line players, backs, wings, others, then shirt number. Numbers: shirt number only."""
    if order is SheetOrder.NUMBERS:
        return tuple(sorted(players, key=lambda p: (_shirt_key(p.number), _surname_key(p))))
    return tuple(sorted(players, key=lambda p: (_role(p), _shirt_key(p.number), _surname_key(p))))


def scorer_places(players: tuple[SquadPlayer, ...]) -> dict[str, int]:
    """Competition ranking (1, 1, 3 …); players without goals have no place."""
    goals = [p.goals for p in players if p.goals]
    return {p.key: 1 + sum(1 for other in goals if other > p.goals) for p in players if p.goals}


def merge_squads(team: SheetTeamData, previous_season: bool) -> tuple[tuple[SquadPlayer, ...], str]:
    if team.current:
        players = list(team.current)
        if previous_season:
            known = {p.key for p in players}
            players += [
                replace(p, matches=None, goals=None, saves=None, shots_faced=None)
                for p in team.previous
                if p.key not in known
            ]
        return tuple(players), "lineups"
    if team.roster:
        return tuple(replace(p, matches=0, goals=0, saves=None, shots_faced=None) for p in team.roster), "roster"
    return (), "none"


def display_name(player: SquadPlayer) -> str:
    if player.last_name:
        return f"{player.last_name.upper()} {player.first_name or ''}".strip()
    return player.name


def _number(value: int | None) -> str:
    return "–" if value is None else str(value)


def sheet_player(player: SquadPlayer, places: dict[str, int], new_group: bool) -> SheetPlayer:
    role = _role(player)
    if player.matches is None:
        average = "–"
    elif player.matches and player.goals is not None:
        average = f"{player.goals / player.matches:.1f}"
    else:
        average = "–"
    if role is LineRole.GOALKEEPER:
        percentage = format_percentage(round(ratio_percentage(player.saves, player.shots_faced) or 0)) if player.shots_faced else ""
    else:
        percentage = ""
    place = places.get(player.key)
    return SheetPlayer(
        number=(player.number or "").strip(),
        name=display_name(player),
        position=POSITION_LETTERS.get(role, ""),
        birth_year=f"{player.birth_year % 100:02d}" if player.birth_year else "",
        matches=_number(player.matches),
        goals=_number(player.goals),
        average=average,
        percentage=percentage or "",
        highlight=place is not None and place <= TOP_SCORERS,
        new_group=new_group,
    )


def sheet_team(letter: str, team: SheetTeamData, order: SheetOrder, previous_season: bool) -> SheetTeam:
    players, source = merge_squads(team, previous_season)
    ordered = order_players(players, order)
    places = scorer_places(ordered)
    rows = []
    for index, player in enumerate(ordered):
        new_group = (
            order is SheetOrder.POSITIONS and index > 0 and _role(player) != _role(ordered[index - 1])
        )
        rows.append(sheet_player(player, places, new_group))
    return SheetTeam(letter=letter, name=team.name, country_code=team.country_code, source=source, players=tuple(rows))


def sheet_layout(player_count: int) -> SheetLayout:
    """Fit both squads on one A4 page: share the space, keep rows readable."""
    if player_count <= 0:
        row = ROW_MAX_MM
    else:
        row = PLAYER_SPACE_MM / player_count - ROW_BORDER_MM
    row = round(min(ROW_MAX_MM, max(ROW_MIN_MM, row)), 2)
    return SheetLayout(row_mm=row, font_pt=round(min(FONT_MAX_PT, row * FONT_PER_MM), 1))


def build_match_sheet(data: MatchSheetData, request: MatchSheetRequest) -> MatchSheet:
    home = sheet_team("A", data.home, request.order, request.previous_season)
    away = sheet_team("B", data.away, request.order, request.previous_season)
    count = max(len(home.players), 1) + max(len(away.players), 1)
    return MatchSheet(
        season_code=data.season_code,
        competition_name=data.competition_name,
        home=home,
        away=away,
        venue=data.venue,
        match_date=request.match_date,
        kickoff=request.kickoff,
        stats_until=data.stats_until,
        layout=sheet_layout(count),
    )
