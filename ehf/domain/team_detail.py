from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from statistics import mean, median

from ehf.domain.gender import gender_label
from ehf.domain.lineup_order import line_role
from ehf.domain.match_detail import format_percentage, ratio_percentage
from ehf.domain.matches import Choice, format_score, format_stage

MISSING = "—"


def _number(value: float | None, digits: int = 1) -> str:
    if value is None:
        return MISSING
    if value == int(value):
        return f"{int(value):,}".replace(",", " ")
    return f"{value:,.{digits}f}".replace(",", " ")


def _percent(made: int | None, attempts: int | None) -> str:
    return format_percentage(ratio_percentage(made, attempts)) or MISSING


def _sum(values: Iterable[int | None]) -> int | None:
    known = [value for value in values if value is not None]
    return sum(known) if known else None


# --- filters ---------------------------------------------------------------


@dataclass(frozen=True)
class TeamDetailFilters:
    season_id: int | None = None
    competition_id: int | None = None
    opponent: str | None = None
    player: str | None = None
    played_only: bool = False


@dataclass(frozen=True)
class TeamSheetFilters:
    season_id: int | None = None
    competition_id: int | None = None
    opponent: str | None = None


@dataclass(frozen=True)
class TeamFilterOptions:
    seasons: tuple[Choice, ...]
    competitions: tuple[Choice, ...]


# --- rows read from the database -------------------------------------------


@dataclass(frozen=True)
class TeamProfile:
    id: int
    ehf_id: str
    name: str
    country_code: str | None
    country_name: str | None
    logo_url: str | None
    website: str | None
    address: str | None
    profile_url: str | None
    genders: str | None

    @property
    def country_text(self) -> str:
        if self.country_name and self.country_code:
            return f"{self.country_name} ({self.country_code})"
        return self.country_name or self.country_code or MISSING

    @property
    def gender_label(self) -> str:
        return gender_label(self.genders or "")


@dataclass(frozen=True)
class TeamEdition:
    season_id: int
    season_code: str
    year_start: int
    competition_id: int
    competition_name: str
    name: str


@dataclass(frozen=True)
class TeamHostVenue:
    venue_id: int
    name: str
    city: str | None
    matches: int
    average_spectators: float | None

    @property
    def average_text(self) -> str:
        return _number(self.average_spectators, 0)


@dataclass(frozen=True)
class TeamMatch:
    match_id: int
    kickoff_at: datetime | None
    season_id: int
    season_code: str
    year_start: int
    competition_id: int
    competition_name: str
    phase: str | None
    group_code: str | None
    side: str
    team_name: str | None
    opponent_id: int | None
    opponent_name: str | None
    home_name: str | None
    away_name: str | None
    score_home: int | None
    score_away: int | None
    regular_home: int | None
    regular_away: int | None
    result_type: str | None
    status: str
    spectators: int | None

    @property
    def is_home(self) -> bool:
        return self.side == "home"

    @property
    def place_text(self) -> str:
        return "home" if self.is_home else "away"

    @property
    def stage_text(self) -> str:
        return format_stage(self.phase, self.group_code)

    @property
    def is_played(self) -> bool:
        return (
            self.status == "played"
            and self.result_type != "walkover"
            and self.regular_home is not None
            and self.regular_away is not None
        )

    @property
    def is_finished(self) -> bool:
        return self.status in {"played", "awarded"} or self.score_home is not None

    def _own(self, home: int | None, away: int | None) -> tuple[int | None, int | None]:
        return (home, away) if self.is_home else (away, home)

    @property
    def goals_for(self) -> int | None:
        return self._own(self.regular_home, self.regular_away)[0] if self.is_played else None

    @property
    def goals_against(self) -> int | None:
        return self._own(self.regular_home, self.regular_away)[1] if self.is_played else None

    @property
    def outcome(self) -> str | None:
        """W / D / L from the regular-time score; None when the match does not count."""
        if not self.is_played:
            return None
        own, other = self.goals_for, self.goals_against
        return "W" if own > other else ("L" if own < other else "D")

    @property
    def decided(self) -> str | None:
        """Who took a draw after extra time or penalties: 'won' / 'lost'."""
        if self.outcome != "D" or self.result_type not in {"extra_time", "penalties"}:
            return None
        own, other = self._own(self.score_home, self.score_away)
        if own is None or other is None or own == other:
            return None
        return "won" if own > other else "lost"

    @property
    def outcome_text(self) -> str:
        if self.outcome:
            return {"W": "Win", "D": "Draw", "L": "Loss"}[self.outcome]
        if self.result_type == "walkover" or self.status == "awarded":
            own, other = self._own(self.score_home, self.score_away)
            if own is not None and other is not None and own != other:
                return "Walkover win" if own > other else "Walkover loss"
            return "Walkover"
        return "No result"

    @property
    def outcome_class(self) -> str:
        return {"W": "ok", "D": "plan", "L": "warn"}.get(self.outcome or "", "")

    @property
    def decided_text(self) -> str | None:
        if self.decided is None:
            return None
        how = "extra time" if self.result_type == "extra_time" else "penalties"
        return f"{self.decided} after {how}"

    @property
    def team_score_text(self) -> str:
        own, other = self._own(self.regular_home, self.regular_away)
        if own is None or other is None:
            own, other = self._own(self.score_home, self.score_away)
        return format_score(own, other)

    @property
    def score_text(self) -> str:
        return format_score(self.score_home, self.score_away, self.result_type)


@dataclass(frozen=True)
class LineupEntry:
    match_id: int
    own: bool
    person_id: int | None
    name: str
    shirt_number: str | None
    position: str | None
    is_goalkeeper: bool
    goals: int | None
    shots: int | None
    yellow_cards: int | None
    two_min_suspensions: int | None
    red_cards: int | None
    saves: int | None
    shots_faced: int | None

    @property
    def keeps_goal(self) -> bool:
        return self.shots_faced is not None and self.shots_faced > 0

    @property
    def key(self) -> str:
        return f"p{self.person_id}" if self.person_id is not None else f"n{self.name}"


def without_missing_saves(entries: Sequence[LineupEntry]) -> tuple[tuple[LineupEntry, ...], frozenset[int]]:
    """Drop goalkeeper numbers from matches where nobody saved anything.

    Some imports (mostly 2022-23) store 0 saves for every goalkeeper of both teams;
    such matches have no save data rather than a 0% save rate.
    """
    saves: Counter[int] = Counter()
    faced: Counter[int] = Counter()
    for entry in entries:
        if entry.keeps_goal:
            saves[entry.match_id] += entry.saves or 0
            faced[entry.match_id] += entry.shots_faced or 0
    missing = {match_id for match_id in faced if faced[match_id] and not saves[match_id]}
    cleaned = tuple(
        replace(entry, saves=None, shots_faced=None) if entry.match_id in missing else entry for entry in entries
    )
    return cleaned, frozenset(missing)


# --- filtering ---------------------------------------------------------------


def _matches_opponent(match: TeamMatch, opponent: str | None) -> bool:
    return not opponent or opponent.casefold() in (match.opponent_name or "").casefold()


def filter_matches(matches: Sequence[TeamMatch], filters: TeamDetailFilters) -> tuple[TeamMatch, ...]:
    return tuple(
        match
        for match in matches
        if (filters.season_id is None or match.season_id == filters.season_id)
        and (filters.competition_id is None or match.competition_id == filters.competition_id)
        and _matches_opponent(match, filters.opponent)
        and (not filters.played_only or match.is_finished)
    )


# --- record and attendance ---------------------------------------------------


@dataclass(frozen=True)
class TeamRecord:
    matches: int
    played: int
    wins: int
    draws: int
    losses: int
    draws_won: int
    draws_lost: int
    others: int
    goals_for: int
    goals_against: int
    home_spectators: tuple[int, ...]
    away_spectators: tuple[int, ...]

    @property
    def win_rate_text(self) -> str:
        return _percent(self.wins, self.played)

    @property
    def goals_text(self) -> str:
        return f"{self.goals_for}:{self.goals_against}" if self.played else MISSING

    @property
    def difference_text(self) -> str:
        return f"{self.goals_for - self.goals_against:+d}" if self.played else MISSING

    @property
    def average_for_text(self) -> str:
        return f"{self.goals_for / self.played:.1f}" if self.played else MISSING

    @property
    def average_against_text(self) -> str:
        return f"{self.goals_against / self.played:.1f}" if self.played else MISSING

    @property
    def decided_text(self) -> str:
        if not (self.draws_won or self.draws_lost):
            return MISSING
        return f"{self.draws_won} won / {self.draws_lost} lost"

    @property
    def others_text(self) -> str:
        return str(self.others) if self.others else MISSING

    @property
    def home_average_text(self) -> str:
        return _number(mean(self.home_spectators), 0) if self.home_spectators else MISSING

    @property
    def away_average_text(self) -> str:
        return _number(mean(self.away_spectators), 0) if self.away_spectators else MISSING

    @property
    def home_sum_text(self) -> str:
        return _number(sum(self.home_spectators)) if self.home_spectators else MISSING


def team_record(matches: Sequence[TeamMatch]) -> TeamRecord:
    played = [match for match in matches if match.is_played]
    outcomes = Counter(match.outcome for match in played)
    decided = Counter(match.decided for match in played if match.decided)
    finished = [match for match in played if match.spectators is not None]
    return TeamRecord(
        matches=len(matches),
        played=len(played),
        wins=outcomes["W"],
        draws=outcomes["D"],
        losses=outcomes["L"],
        draws_won=decided["won"],
        draws_lost=decided["lost"],
        others=sum(1 for match in matches if not match.is_played and match.is_finished),
        goals_for=sum(match.goals_for or 0 for match in played),
        goals_against=sum(match.goals_against or 0 for match in played),
        home_spectators=tuple(match.spectators for match in finished if match.is_home),
        away_spectators=tuple(match.spectators for match in finished if not match.is_home),
    )


@dataclass(frozen=True)
class PlaceAttendance:
    matches: int
    values: tuple[int, ...]
    record: TeamMatch | None

    @property
    def average_text(self) -> str:
        return _number(mean(self.values), 0) if self.values else MISSING

    @property
    def median_text(self) -> str:
        return _number(median(self.values), 0) if self.values else MISSING

    @property
    def sum_text(self) -> str:
        return _number(sum(self.values)) if self.values else MISSING

    @property
    def record_text(self) -> str:
        return _number(self.record.spectators) if self.record else MISSING

    @property
    def record_note(self) -> str | None:
        if self.record is None:
            return None
        date = self.record.kickoff_at.strftime("%Y-%m-%d") if self.record.kickoff_at else ""
        return f"vs {self.record.opponent_name or MISSING} {date}".strip()

    @property
    def coverage_text(self) -> str:
        return f"{len(self.values)} / {self.matches}"


@dataclass(frozen=True)
class TeamAttendance:
    home: PlaceAttendance
    away: PlaceAttendance

    @property
    def has_data(self) -> bool:
        return bool(self.home.values or self.away.values)


def _place_attendance(matches: Sequence[TeamMatch]) -> PlaceAttendance:
    known = [match for match in matches if match.spectators is not None]
    return PlaceAttendance(
        matches=len(matches),
        values=tuple(match.spectators for match in known),
        record=max(known, key=lambda match: match.spectators, default=None),
    )


def team_attendance(matches: Sequence[TeamMatch]) -> TeamAttendance:
    played = [match for match in matches if match.is_played]
    return TeamAttendance(
        home=_place_attendance([match for match in played if match.is_home]),
        away=_place_attendance([match for match in played if not match.is_home]),
    )


# --- seasons -----------------------------------------------------------------


@dataclass(frozen=True)
class TeamSeasonRow:
    season_id: int
    season_code: str
    competition_name: str
    team_name: str
    is_season: bool
    record: TeamRecord


def season_rows(matches: Sequence[TeamMatch], editions: Sequence[TeamEdition]) -> tuple[TeamSeasonRow, ...]:
    rows: list[TeamSeasonRow] = []
    by_season: dict[int, list[TeamEdition]] = {}
    for edition in editions:
        by_season.setdefault(edition.season_id, []).append(edition)
    for season_id, season_editions in sorted(by_season.items(), key=lambda item: -item[1][0].year_start):
        season_matches = [match for match in matches if match.season_id == season_id]
        first = season_editions[0]
        rows.append(
            TeamSeasonRow(
                season_id=season_id,
                season_code=first.season_code,
                competition_name=", ".join(edition.competition_name for edition in season_editions),
                team_name=", ".join(dict.fromkeys(edition.name for edition in season_editions)),
                is_season=True,
                record=team_record(season_matches),
            )
        )
        if len(season_editions) > 1:
            for edition in season_editions:
                rows.append(
                    TeamSeasonRow(
                        season_id=season_id,
                        season_code=edition.season_code,
                        competition_name=edition.competition_name,
                        team_name=edition.name,
                        is_season=False,
                        record=team_record(
                            [m for m in season_matches if m.competition_id == edition.competition_id]
                        ),
                    )
                )
    return tuple(rows)


@dataclass(frozen=True)
class TeamName:
    name: str
    seasons: tuple[str, ...]

    @property
    def seasons_text(self) -> str:
        if len(self.seasons) > 2:
            return f"{self.seasons[-1]} – {self.seasons[0]}"
        return ", ".join(self.seasons)


def name_history(editions: Sequence[TeamEdition]) -> tuple[TeamName, ...]:
    seasons: dict[str, list[str]] = {}
    for edition in editions:
        codes = seasons.setdefault(edition.name, [])
        if edition.season_code not in codes:
            codes.append(edition.season_code)
    return tuple(TeamName(name, tuple(codes)) for name, codes in seasons.items())


# --- players -----------------------------------------------------------------


@dataclass(frozen=True)
class TeamPlayerRow:
    person_id: int | None
    name: str
    numbers: tuple[str, ...]
    position: str | None
    is_goalkeeper: bool
    matches: int
    goals: int | None
    shots: int | None
    yellow_cards: int | None
    two_min_suspensions: int | None
    red_cards: int | None
    saves: int | None
    shots_faced: int | None
    seasons: tuple[str, ...]
    last_match: TeamMatch | None

    @property
    def average_text(self) -> str:
        return f"{self.goals / self.matches:.2f}" if self.goals is not None and self.matches else MISSING

    @property
    def shot_percentage_text(self) -> str:
        return _percent(self.goals, self.shots)

    @property
    def save_percentage_text(self) -> str:
        return _percent(self.saves, self.shots_faced)

    @property
    def seasons_text(self) -> str:
        return ", ".join(self.seasons)

    @property
    def last_match_text(self) -> str:
        if self.last_match is None or self.last_match.kickoff_at is None:
            return MISSING
        return self.last_match.kickoff_at.strftime("%Y-%m-%d")


def _main_position(entries: Sequence[LineupEntry]) -> str | None:
    counts = Counter(entry.position.strip() for entry in entries if (entry.position or "").strip())
    if not counts:
        return "Goalkeeper" if any(entry.is_goalkeeper for entry in entries) else None
    return sorted(counts, key=lambda position: (-counts[position], position))[0]


def _grouped(entries: Iterable[LineupEntry]) -> dict[str, list[LineupEntry]]:
    groups: dict[str, list[LineupEntry]] = {}
    for entry in entries:
        groups.setdefault(entry.key, []).append(entry)
    return groups


def _numbers(entries: Sequence[LineupEntry]) -> tuple[str, ...]:
    numbers = {entry.shirt_number.strip() for entry in entries if (entry.shirt_number or "").strip()}
    return tuple(sorted(numbers, key=lambda number: (not number.isdigit(), int(number) if number.isdigit() else 0, number)))


def player_rows(
    entries: Sequence[LineupEntry], matches: Sequence[TeamMatch], player: str | None = None
) -> tuple[TeamPlayerRow, ...]:
    by_id = {match.match_id: match for match in matches}
    own = [entry for entry in entries if entry.own and entry.match_id in by_id]
    if player:
        own = [entry for entry in own if player.casefold() in entry.name.casefold()]
    rows = []
    for group in _grouped(own).values():
        played = [by_id[entry.match_id] for entry in group]
        played.sort(key=lambda match: (match.kickoff_at is None, match.kickoff_at or datetime.min))
        rows.append(
            TeamPlayerRow(
                person_id=group[-1].person_id,
                name=group[-1].name,
                numbers=_numbers(group),
                position=_main_position(group),
                is_goalkeeper=any(entry.is_goalkeeper or entry.keeps_goal for entry in group),
                matches=len({entry.match_id for entry in group}),
                goals=_sum(entry.goals for entry in group),
                shots=_sum(entry.shots for entry in group),
                yellow_cards=_sum(entry.yellow_cards for entry in group),
                two_min_suspensions=_sum(entry.two_min_suspensions for entry in group),
                red_cards=_sum(entry.red_cards for entry in group),
                saves=_sum(entry.saves for entry in group),
                shots_faced=_sum(entry.shots_faced for entry in group),
                seasons=tuple(dict.fromkeys(match.season_code for match in reversed(played))),
                last_match=played[-1] if played and played[-1].kickoff_at else None,
            )
        )
    rows.sort(key=lambda row: (-(row.goals or 0), row.name.casefold()))
    return tuple(rows)


# --- goalkeepers -------------------------------------------------------------


@dataclass(frozen=True)
class SaveLine:
    saves: int
    shots_faced: int

    @property
    def text(self) -> str:
        return f"{self.saves}/{self.shots_faced}" if self.shots_faced else MISSING

    @property
    def percentage_text(self) -> str:
        return _percent(self.saves, self.shots_faced)


def _save_line(entries: Iterable[LineupEntry]) -> SaveLine:
    keepers = [entry for entry in entries if entry.keeps_goal]
    return SaveLine(
        saves=sum(entry.saves or 0 for entry in keepers),
        shots_faced=sum(entry.shots_faced or 0 for entry in keepers),
    )


@dataclass(frozen=True)
class GoalkeeperMatch:
    match: TeamMatch
    saves: int
    shots_faced: int

    @property
    def percentage(self) -> float:
        return self.saves * 100 / self.shots_faced

    @property
    def text(self) -> str:
        return f"{self.saves}/{self.shots_faced} ({_percent(self.saves, self.shots_faced)})"


@dataclass(frozen=True)
class TeamGoalkeeperRow:
    person_id: int | None
    name: str
    numbers: tuple[str, ...]
    matches: int
    line: SaveLine
    match_percentages: tuple[float, ...]
    best: GoalkeeperMatch | None
    seasons: tuple[str, ...]

    @property
    def average_saves_text(self) -> str:
        return f"{self.line.saves / self.matches:.1f}" if self.matches else MISSING

    @property
    def median_text(self) -> str:
        return format_percentage(round(median(self.match_percentages), 1)) or MISSING if self.match_percentages else MISSING

    @property
    def seasons_text(self) -> str:
        return ", ".join(self.seasons)


BEST_KEEPER_MIN_SHOTS = 100
BEST_MATCH_MIN_SHOTS = 10


@dataclass(frozen=True)
class GoalkeeperSplit:
    label: str
    is_season: bool
    matches: int
    own: SaveLine
    opponents: SaveLine


@dataclass(frozen=True)
class GoalkeeperMatchRow:
    match: TeamMatch
    own: SaveLine
    opponents: SaveLine
    keepers: tuple[GoalkeeperMatch, ...]
    keeper_names: tuple[str, ...]


@dataclass(frozen=True)
class TeamGoalkeeping:
    matches: int
    own: SaveLine
    opponents: SaveLine
    keepers: tuple[TeamGoalkeeperRow, ...]
    splits: tuple[GoalkeeperSplit, ...]
    by_match: tuple[GoalkeeperMatchRow, ...]
    best_match: GoalkeeperMatchRow | None
    worst_match: GoalkeeperMatchRow | None
    missing_matches: int = 0

    @property
    def has_data(self) -> bool:
        return self.own.shots_faced > 0

    @property
    def by_match_id(self) -> dict[int, GoalkeeperMatchRow]:
        return {row.match.match_id: row for row in self.by_match}

    @property
    def most_shots(self) -> TeamGoalkeeperRow | None:
        return self.keepers[0] if self.keepers else None

    @property
    def best_keeper(self) -> TeamGoalkeeperRow | None:
        ranked = [row for row in self.keepers if row.line.shots_faced >= BEST_KEEPER_MIN_SHOTS]
        return max(ranked, key=lambda row: row.line.saves / row.line.shots_faced, default=None)

    @property
    def difference_text(self) -> str:
        own = ratio_percentage(self.own.saves, self.own.shots_faced)
        other = ratio_percentage(self.opponents.saves, self.opponents.shots_faced)
        if own is None or other is None:
            return MISSING
        return f"{own - other:+.1f} pp"


def team_goalkeeping(entries: Sequence[LineupEntry], matches: Sequence[TeamMatch]) -> TeamGoalkeeping:
    by_id = {match.match_id: match for match in matches}
    relevant = [entry for entry in entries if entry.match_id in by_id and entry.keeps_goal]
    own = [entry for entry in relevant if entry.own]
    opponents = [entry for entry in relevant if not entry.own]

    keepers = []
    for group in _grouped(own).values():
        per_match = [
            GoalkeeperMatch(by_id[entry.match_id], entry.saves or 0, entry.shots_faced or 0) for entry in group
        ]
        ordered = sorted(per_match, key=lambda item: item.match.kickoff_at or datetime.min, reverse=True)
        keepers.append(
            TeamGoalkeeperRow(
                person_id=group[-1].person_id,
                name=group[-1].name,
                numbers=_numbers(group),
                matches=len(per_match),
                line=_save_line(group),
                match_percentages=tuple(item.percentage for item in per_match),
                best=max(per_match, key=lambda item: (item.saves, item.percentage), default=None),
                seasons=tuple(dict.fromkeys(item.match.season_code for item in ordered)),
            )
        )
    keepers.sort(key=lambda row: (-row.line.shots_faced, row.name.casefold()))

    def split(label: str, is_season: bool, chosen: Sequence[TeamMatch]) -> GoalkeeperSplit:
        ids = {match.match_id for match in chosen}
        return GoalkeeperSplit(
            label=label,
            is_season=is_season,
            matches=len({entry.match_id for entry in own if entry.match_id in ids}),
            own=_save_line(entry for entry in own if entry.match_id in ids),
            opponents=_save_line(entry for entry in opponents if entry.match_id in ids),
        )

    splits: list[GoalkeeperSplit] = []
    seasons: dict[int, list[TeamMatch]] = {}
    for match in sorted(matches, key=lambda match: -match.year_start):
        seasons.setdefault(match.season_id, []).append(match)
    for season_matches in seasons.values():
        splits.append(split(season_matches[0].season_code, True, season_matches))
        competitions = dict.fromkeys(match.competition_name for match in season_matches)
        if len(competitions) > 1:
            for name in competitions:
                splits.append(split(name, False, [m for m in season_matches if m.competition_name == name]))

    rows = []
    for match in sorted(matches, key=lambda match: match.kickoff_at or datetime.min, reverse=True):
        mine = [entry for entry in own if entry.match_id == match.match_id]
        if not mine:
            continue
        rows.append(
            GoalkeeperMatchRow(
                match=match,
                own=_save_line(mine),
                opponents=_save_line(entry for entry in opponents if entry.match_id == match.match_id),
                keepers=tuple(GoalkeeperMatch(match, e.saves or 0, e.shots_faced or 0) for e in mine),
                keeper_names=tuple(entry.name for entry in mine),
            )
        )
    rated = [row for row in rows if row.own.shots_faced >= BEST_MATCH_MIN_SHOTS]
    return TeamGoalkeeping(
        matches=len(rows),
        own=_save_line(own),
        opponents=_save_line(opponents),
        keepers=tuple(keepers),
        splits=tuple(split for split in splits if split.matches),
        by_match=tuple(rows),
        best_match=max(rated, key=lambda row: row.own.saves / row.own.shots_faced, default=None),
        worst_match=min(rated, key=lambda row: row.own.saves / row.own.shots_faced, default=None),
    )


# --- season sheet ------------------------------------------------------------


@dataclass(frozen=True)
class SheetCell:
    matches: int
    goals: int | None
    shots: int | None
    yellow_cards: int
    two_min_suspensions: int
    red_cards: int
    saves: int | None
    shots_faced: int | None

    @property
    def penalties_text(self) -> str:
        parts = []
        if self.two_min_suspensions:
            parts.append(f"{self.two_min_suspensions}×2′")
        if self.yellow_cards:
            parts.append(f"{self.yellow_cards}Y" if self.yellow_cards > 1 else "Y")
        if self.red_cards:
            parts.append(f"{self.red_cards}R" if self.red_cards > 1 else "R")
        return " ".join(parts)

    @property
    def saves_text(self) -> str | None:
        if not self.shots_faced:
            return None
        return f"{self.saves or 0}/{self.shots_faced}"

    @property
    def save_percentage_text(self) -> str:
        return _percent(self.saves, self.shots_faced)

    @property
    def shot_percentage_text(self) -> str:
        return _percent(self.goals, self.shots)

    @property
    def description(self) -> str:
        parts = [f"goals {self.goals if self.goals is not None else MISSING}"]
        if self.shots is not None:
            parts.append(f"shots {self.shots}")
        if self.penalties_text:
            parts.append(self.penalties_text)
        if self.saves_text:
            parts.append(f"saves {self.saves_text} ({self.save_percentage_text})")
        return " · ".join(parts)


def sheet_cell(entries: Sequence[LineupEntry]) -> SheetCell:
    keepers = [entry for entry in entries if entry.keeps_goal]
    return SheetCell(
        matches=len({entry.match_id for entry in entries}),
        goals=_sum(entry.goals for entry in entries),
        shots=_sum(entry.shots for entry in entries),
        yellow_cards=sum(entry.yellow_cards or 0 for entry in entries),
        two_min_suspensions=sum(entry.two_min_suspensions or 0 for entry in entries),
        red_cards=sum(entry.red_cards or 0 for entry in entries),
        saves=_sum(entry.saves for entry in keepers),
        shots_faced=_sum(entry.shots_faced for entry in keepers),
    )


@dataclass(frozen=True)
class SheetRow:
    person_id: int | None
    name: str
    numbers: tuple[str, ...]
    position: str | None
    is_goalkeeper: bool
    cells: tuple[SheetCell | None, ...]
    total: SheetCell


@dataclass(frozen=True)
class TeamSeasonSheet:
    season_code: str | None
    matches: tuple[TeamMatch, ...]
    rows: tuple[SheetRow, ...]
    match_totals: tuple[SheetCell, ...]
    total: SheetCell


def season_sheet(
    entries: Sequence[LineupEntry], matches: Sequence[TeamMatch], season_code: str | None
) -> TeamSeasonSheet:
    by_id = {match.match_id: match for match in matches}
    own = [entry for entry in entries if entry.own and entry.match_id in by_id]
    with_lineup = {entry.match_id for entry in own}
    columns = tuple(
        sorted(
            (match for match in matches if match.match_id in with_lineup),
            key=lambda match: (match.kickoff_at is None, match.kickoff_at or datetime.min, match.match_id),
        )
    )
    rows = []
    for group in _grouped(own).values():
        per_match = {entry.match_id: entry for entry in group}
        position = _main_position(group)
        is_goalkeeper = any(entry.is_goalkeeper or entry.keeps_goal for entry in group)
        rows.append(
            SheetRow(
                person_id=group[-1].person_id,
                name=group[-1].name,
                numbers=_numbers(group),
                position=position,
                is_goalkeeper=is_goalkeeper,
                cells=tuple(
                    sheet_cell([per_match[match.match_id]]) if match.match_id in per_match else None
                    for match in columns
                ),
                total=sheet_cell(group),
            )
        )
    rows.sort(
        key=lambda row: (
            line_role(row.position, row.is_goalkeeper),
            -(row.total.goals or 0),
            row.name.casefold(),
        )
    )
    return TeamSeasonSheet(
        season_code=season_code,
        matches=columns,
        rows=tuple(rows),
        match_totals=tuple(
            sheet_cell([entry for entry in own if entry.match_id == match.match_id]) for match in columns
        ),
        total=sheet_cell(own),
    )


# --- the whole card ----------------------------------------------------------


@dataclass(frozen=True)
class TeamCardData:
    profile: TeamProfile
    editions: tuple[TeamEdition, ...]
    venues: tuple[TeamHostVenue, ...]
    matches: tuple[TeamMatch, ...]
    entries: tuple[LineupEntry, ...]


@dataclass(frozen=True)
class TeamCard:
    profile: TeamProfile
    editions: tuple[TeamEdition, ...]
    names: tuple[TeamName, ...]
    venues: tuple[TeamHostVenue, ...]
    all_matches: tuple[TeamMatch, ...]
    attendance: TeamAttendance
    seasons: tuple[TeamSeasonRow, ...]
    options: TeamFilterOptions
    filters: TeamDetailFilters
    matches: tuple[TeamMatch, ...]
    match_attendance: TeamAttendance
    match_record: TeamRecord
    players: tuple[TeamPlayerRow, ...]
    goalkeeping: TeamGoalkeeping
    sheet_filters: TeamSheetFilters
    sheet: TeamSeasonSheet

    @property
    def season_range_text(self) -> str:
        codes = [edition.season_code for edition in self.editions]
        if not codes:
            return MISSING
        return codes[0] if len(set(codes)) == 1 else f"{codes[-1]} – {codes[0]}"

    @property
    def season_count(self) -> int:
        return len({edition.season_id for edition in self.editions})
