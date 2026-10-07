"""Match statistics tab: team and player metrics read from the play-by-play.

Built on the match-summary rules (``match_summary``), plus three model-based figures:

- expected goals (xG): every shot is worth the share of shots from that zone that were goals in the
  reference matches (same competition, see ``Baseline``); fast breaks are one zone of their own
- goals saved above average (GSAA): a goalkeeper's saves minus the saves an average goalkeeper of the
  competition makes on the same shots (by zone)
- win probability added (WPA): how much a player's goals moved his team's win probability
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from ehf.domain.lineup_order import LineRole, line_role
from ehf.domain.match_summary import (
    SIDES,
    Baseline,
    MatchEvents,
    MatchSummary,
    Moment,
    Person,
    Shot,
    clock,
    match_events,
    shot_zone_key,
    win_probability,
)

ZONE_ORDER = ("LW", "LLD", "LSD", "CLD", "CSD", "RSD", "RLD", "RW", "PTY", "FB")
ZONE_NAMES = {
    "LW": "Left wing",
    "LLD": "Left 9 m",
    "LSD": "Left 6 m",
    "CLD": "Centre 9 m",
    "CSD": "Centre 6 m",
    "RSD": "Right 6 m",
    "RLD": "Right 9 m",
    "RW": "Right wing",
    "PTY": "7 m",
    "FB": "Fast break",
    "?": "Not recorded",
}
RESULTS = ("GOAL", "SAVE", "MISS", "POST", "BLC")
CLUTCH_WINDOW = 10 * 60
CLUTCH_MARGIN = 2


@dataclass(frozen=True)
class LineupEntry:
    side: str
    person_id: int | None
    number: str
    name: str
    goalkeeper: bool
    position: str | None = None


@dataclass(frozen=True)
class PlayerEvent:
    seconds: int
    kind: str
    title: str
    detail: str
    score: str
    side: str

    @property
    def clock(self) -> str:
        return clock(self.seconds)

    @property
    def minute(self) -> int:
        # 0:01–1:00 is the 1st minute, so the final whistle at 60:00 is still the 60th
        return max(1, -(-self.seconds // 60))


@dataclass
class PlayerStats:
    side: str
    number: str
    name: str
    person_id: int | None
    goalkeeper: bool
    position: str | None = None
    goals: int = 0
    shots: int = 0
    seven_goals: int = 0
    seven_shots: int = 0
    fast_break_goals: int = 0
    assists: int = 0
    turnovers: int = 0
    steals: int = 0
    blocks: int = 0
    sevens_won: int = 0
    suspensions: int = 0
    yellow: int = 0
    red: int = 0
    xg: float = 0.0
    wpa: float = 0.0
    clutch_goals: int = 0
    saves: int = 0
    faced: int = 0
    seven_saves: int = 0
    seven_faced: int = 0
    expected_saves: float = 0.0
    events: list[PlayerEvent] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.side}-{self.person_id or self.number}"

    @property
    def role(self) -> LineRole:
        return line_role(self.position, self.goalkeeper)

    @property
    def rate(self) -> float | None:
        return self.goals / self.shots if self.shots else None

    @property
    def save_rate(self) -> float | None:
        return self.saves / self.faced if self.faced else None

    @property
    def goals_above_expected(self) -> float:
        return self.goals - self.xg

    @property
    def gsaa(self) -> float:
        return self.saves - self.expected_saves

    @property
    def involvement(self) -> int:
        return self.goals + self.assists

    @property
    def actions(self) -> int:
        return len(self.events)

    @property
    def active(self) -> bool:
        return bool(self.events)

    @property
    def span(self) -> str:
        if not self.events:
            return ""
        return f"{self.events[0].minute}'–{self.events[-1].minute}'"


@dataclass(frozen=True)
class ZoneShooter:
    number: str
    name: str
    shots: int
    goals: int

    @property
    def rate(self) -> float | None:
        return self.goals / self.shots if self.shots else None


@dataclass(frozen=True)
class ZoneLine:
    zone: str
    name: str
    shots: int
    goals: int
    xg: float
    average: float | None
    shooters: tuple[ZoneShooter, ...] = ()

    @property
    def rate(self) -> float | None:
        return self.goals / self.shots if self.shots else None


@dataclass(frozen=True)
class TeamShooting:
    side: str
    goals: int
    shots: int
    xg: float
    zones: tuple[ZoneLine, ...]
    outcomes: dict[str, int]
    possessions: int | None

    @property
    def goals_above_expected(self) -> float:
        return self.goals - self.xg


@dataclass(frozen=True)
class SaveMark:
    seconds: int
    saved: bool
    seven: bool


@dataclass(frozen=True)
class MatchStatistics:
    summary: MatchSummary
    shooting: dict[str, TeamShooting]
    players: dict[str, tuple[PlayerStats, ...]]
    save_marks: dict[str, tuple[tuple[PlayerStats, tuple[SaveMark, ...]], ...]]
    end_seconds: int
    xg_ready: bool

    @property
    def keepers(self) -> dict[str, tuple[PlayerStats, ...]]:
        return {side: tuple(p for p in self.players[side] if p.faced) for side in SIDES}

    def team_keeping(self, side: str) -> PlayerStats:
        """All goalkeepers of a team as one line (saves, shots on target, GSAA, 7 m)."""
        total = PlayerStats(side=side, number="", name="All goalkeepers", person_id=None, goalkeeper=True)
        for keeper in self.keepers[side]:
            total.saves += keeper.saves
            total.faced += keeper.faced
            total.seven_saves += keeper.seven_saves
            total.seven_faced += keeper.seven_faced
            total.expected_saves += keeper.expected_saves
            total.events.extend(event for event in keeper.events if event.kind in ("save", "conceded"))
        total.events.sort(key=lambda event: event.seconds)
        return total

    def team_save_marks(self, side: str) -> tuple[SaveMark, ...]:
        marks = [mark for _, keeper_marks in self.save_marks[side] for mark in keeper_marks]
        return tuple(sorted(marks, key=lambda mark: mark.seconds))


def build_statistics(
    summary: MatchSummary,
    actions,
    lineup: Sequence[LineupEntry],
    base: Baseline | None,
) -> MatchStatistics:
    events = match_events(actions)
    end = summary.flow.end_seconds
    rates = base.values if base else {}
    overall = rates.get("shooting") or _overall(events)
    players = _players(events, lineup)

    def xg_of(shot: Shot) -> float:
        return rates.get(f"xg_{shot_zone_key(shot)}", overall)

    def save_of(shot: Shot) -> float:
        return rates.get(f"zone_save_{shot_zone_key(shot)}", rates.get("saving", 0.27))

    scores = _score_before(events)
    margin_before = {}
    previous = 0
    for goal in events.goals:
        margin_before[id(goal)] = previous
        previous = goal.home - goal.away

    zone_shooters: dict[tuple[str, str], dict[str, list]] = {}
    for shot in events.shots:
        score = scores.get(id(shot), "")
        shooter = _find(players, shot.shooter)
        if shooter is not None:
            line = zone_shooters.setdefault((shot.side, shot_zone_key(shot)), {}).setdefault(
                shooter.key, [shooter.number, shooter.name, 0, 0]
            )
            line[2] += 1
            line[3] += shot.is_goal
            shooter.shots += 1
            shooter.xg += xg_of(shot)
            shooter.seven_shots += shot.is_penalty
            if shot.is_goal:
                shooter.goals += 1
                shooter.seven_goals += shot.is_penalty
                shooter.fast_break_goals += shot.fast_break
                before = margin_before.get(id(shot), 0)
                left = end - shot.seconds
                after = shot.home - shot.away
                delta = win_probability(after, left) - win_probability(before, left)
                shooter.wpa += delta if shot.side == "home" else -delta
                if shot.seconds >= end - CLUTCH_WINDOW and abs(before) <= CLUTCH_MARGIN:
                    shooter.clutch_goals += 1
            shooter.events.append(_shot_event(shot, score))
        helper = _find(players, shot.assist) if shot.is_goal else None
        if helper is not None:
            helper.assists += 1
            helper.events.append(
                PlayerEvent(shot.seconds, "assist", "Assist", _who(shot.shooter), f"{shot.home}:{shot.away}", helper.side)
            )
        keeper = _find(players, shot.keeper)
        if keeper is not None and shot.result in ("GOAL", "SAVE"):
            keeper.faced += 1
            keeper.expected_saves += save_of(shot)
            keeper.seven_faced += shot.is_penalty
            if shot.result == "SAVE":
                keeper.saves += 1
                keeper.seven_saves += shot.is_penalty
            keeper.events.append(
                PlayerEvent(
                    shot.seconds,
                    "save" if shot.result == "SAVE" else "conceded",
                    ("7m save" if shot.is_penalty else "Save") if shot.result == "SAVE" else "Conceded",
                    _join(_who(shot.shooter), ZONE_NAMES.get(shot_zone_key(shot), "")),
                    f"{shot.home}:{shot.away}",
                    keeper.side,
                )
            )

    for kind, title, moments, attr in (
        ("turnover", "Turnover", events.turnovers, "turnovers"),
        ("steal", "Steal", events.steals, "steals"),
        ("block", "Block", events.blocks, "blocks"),
        ("seven_won", "7m won", events.sevens_won, "sevens_won"),
        ("suspension", "2 min", events.suspensions, "suspensions"),
        ("yellow", "Yellow card", events.yellow_cards, "yellow"),
        ("red", "Red card", events.red_cards, "red"),
    ):
        for moment in moments:
            player = _find(players, moment.person)
            if player is None:
                continue
            setattr(player, attr, getattr(player, attr) + 1)
            player.events.append(PlayerEvent(moment.seconds, kind, title, "", _score_at(events, moment), player.side))

    for side_players in players.values():
        for player in side_players.values():
            player.events.sort(key=lambda event: event.seconds)

    ordered = {side: tuple(sorted(players[side].values(), key=_order)) for side in SIDES}
    return MatchStatistics(
        summary=summary,
        shooting={side: _team_shooting(events, side, xg_of, rates, zone_shooters) for side in SIDES},
        players=ordered,
        save_marks={
            side: tuple(
                (keeper, tuple(_save_marks(events, keeper)))
                for keeper in ordered[side]
                if keeper.faced
            )
            for side in SIDES
        },
        end_seconds=end,
        xg_ready=bool(base and any(key.startswith("xg_") for key in rates)),
    )


def _overall(events: MatchEvents) -> float:
    shots = len(events.shots)
    return sum(1 for shot in events.shots if shot.is_goal) / shots if shots else 0.6


def _players(events: MatchEvents, lineup: Sequence[LineupEntry]) -> dict[str, dict[tuple, PlayerStats]]:
    players: dict[str, dict[tuple, PlayerStats]] = {side: {} for side in SIDES}
    for entry in lineup:
        players[entry.side][(entry.side, entry.number)] = PlayerStats(
            side=entry.side,
            number=entry.number,
            name=entry.name,
            person_id=entry.person_id,
            goalkeeper=entry.goalkeeper,
            position=entry.position,
        )
    return players


def _find(players: dict[str, dict[tuple, PlayerStats]], person: Person | None) -> PlayerStats | None:
    if person is None:
        return None
    side = players[person.side]
    if person.person_id is not None:
        for player in side.values():
            if player.person_id == person.person_id:
                return player
    found = side.get((person.side, person.number))
    if found is None:
        found = side[(person.side, person.number)] = PlayerStats(
            side=person.side, number=person.number, name=person.name, person_id=person.person_id, goalkeeper=False
        )
    return found


def _order(player: PlayerStats) -> tuple:
    """Like the Lineup tab: goalkeepers, line players, backs, wings, others; then shirt number."""
    return (player.role, int(player.number) if player.number.isdigit() else 999, player.name)


def _shot_event(shot: Shot, score: str) -> PlayerEvent:
    zone = ZONE_NAMES.get(shot_zone_key(shot), "")
    if shot.is_goal:
        title = "7m goal" if shot.is_penalty else "Goal"
        detail = _join("assist " + _who(shot.assist) if shot.assist else "", "fast break" if shot.fast_break else "", zone)
        return PlayerEvent(shot.seconds, "goal", title, detail, f"{shot.home}:{shot.away}", shot.side)
    titles = {"SAVE": "Saved", "MISS": "Missed", "POST": "Post", "BLC": "Blocked"}
    detail = _join("by " + _who(shot.keeper) if shot.result == "SAVE" and shot.keeper else "", zone)
    return PlayerEvent(shot.seconds, "shot", titles.get(shot.result, "Shot"), detail, score, shot.side)


def _who(person: Person | None) -> str:
    return person.label if person else ""


def _join(*parts: str) -> str:
    return " · ".join(part for part in parts if part)


def _score_before(events: MatchEvents) -> dict[int, str]:
    return {id(shot): f"{shot.home}:{shot.away}" for shot in events.shots}


def _score_at(events: MatchEvents, moment: Moment) -> str:
    score = "0:0"
    for goal in events.goals:
        if goal.seconds > moment.seconds:
            break
        score = f"{goal.home}:{goal.away}"
    return score


def _team_shooting(events: MatchEvents, side: str, xg_of, rates: dict[str, float], zone_shooters) -> TeamShooting:
    own = [shot for shot in events.shots if shot.side == side]
    zones = []
    for zone in ZONE_ORDER + ("?",):
        picked = [shot for shot in own if shot_zone_key(shot) == zone]
        if not picked:
            continue
        zones.append(
            ZoneLine(
                zone=zone,
                name=ZONE_NAMES[zone],
                shots=len(picked),
                goals=sum(1 for shot in picked if shot.is_goal),
                xg=sum(xg_of(shot) for shot in picked),
                average=rates.get(f"xg_{zone}"),
                shooters=tuple(
                    sorted(
                        (ZoneShooter(*line) for line in zone_shooters.get((side, zone), {}).values()),
                        key=lambda s: (-s.goals, -s.shots, s.name),
                    )
                ),
            )
        )
    outcomes = {result: sum(1 for shot in own if shot.result == result) for result in RESULTS}
    turnovers = sum(1 for item in events.turnovers if item.side == side) if events.has_turnovers else None
    return TeamShooting(
        side=side,
        goals=outcomes["GOAL"],
        shots=len(own),
        xg=sum(xg_of(shot) for shot in own),
        zones=tuple(zones),
        outcomes=outcomes,
        possessions=len(own) + turnovers if turnovers is not None else None,
    )


def _save_marks(events: MatchEvents, keeper: PlayerStats):
    for shot in events.shots:
        if shot.keeper is None or shot.result not in ("GOAL", "SAVE") or shot.keeper.side != keeper.side:
            continue
        same = (shot.keeper.person_id is not None and shot.keeper.person_id == keeper.person_id) or (
            shot.keeper.number == keeper.number
        )
        if same:
            yield SaveMark(shot.seconds, shot.result == "SAVE", shot.is_penalty)
