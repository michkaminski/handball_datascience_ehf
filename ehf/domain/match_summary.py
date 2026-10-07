"""One-page match summary built from the play-by-play feed (ehf.match_action).

The feed changed over the seasons: up to 2024-25 a fast-break goal is a SHOT followed by a
``TO``/``FB`` companion row and goalkeeper swaps (``GKS``) are logged; from 2025-26 turnovers are
real ``TO`` rows and fast breaks are not marked. 2021-22 has no turnovers at all and sends a
fast-break shot four times, once per zone code ``FB``/``FBL``/``FBR``/``FBC``. Figures the feed
of a match does not carry come back as ``None``.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

SIDES = ("home", "away")
REGULATION = 60 * 60
HALF = 30 * 60
SHOOTOUT_PERIODS = frozenset({"PSO", "SO", "P7"})
MAP_ZONES = ("LW", "LLD", "LSD", "CLD", "CSD", "RSD", "RLD", "RW")
PENALTY_ZONE = "PTY"
FAST_BREAK_ZONES = frozenset({"FB", "FBL", "FBR", "FBC"})
ZONE_GROUPS = (
    ("wings", ("LW", "RW")),
    ("six", ("LSD", "CSD", "RSD")),
    ("nine", ("LLD", "CLD", "RLD")),
    ("seven", (PENALTY_ZONE,)),
)
SUSPENSION_SECONDS = 120
TIMEOUT_WINDOW = 3 * 60
MIN_RUN = 3
KEY_MOMENTS = 3

# Win probability of the home team: logistic on lead / sqrt(minutes left + 1) and a home edge
# that fades with the clock. Fitted on 1682 EHF matches 2021–2027 (state sampled every minute,
# draw = 0.5); calibration within 3 points in every decile.
WIN_LEAD = 2.858
WIN_HOME = 0.4564


@dataclass(frozen=True)
class TickerActor:
    side: str
    role: str | None
    number: str | None
    name: str | None
    person_id: int | None = None


@dataclass(frozen=True)
class TickerAction:
    seq: int
    code: str
    result: str | None
    zone: str | None
    add: str | None
    period: str | None
    seconds: int
    home: int
    away: int
    actors: tuple[TickerActor, ...]


@dataclass(frozen=True)
class Person:
    side: str
    number: str
    name: str
    # not part of equality: a few feed rows carry the name without the link to ehf.person
    person_id: int | None = field(default=None, compare=False)

    @property
    def label(self) -> str:
        return f"{self.number} {self.name}".strip()


@dataclass(frozen=True)
class Shot:
    seconds: int
    side: str
    result: str
    zone: str | None
    shooter: Person | None
    keeper: Person | None
    assist: Person | None
    home: int
    away: int
    fast_break: bool = False

    @property
    def is_goal(self) -> bool:
        return self.result == "GOAL"

    @property
    def is_penalty(self) -> bool:
        return self.zone == PENALTY_ZONE


@dataclass(frozen=True)
class Moment:
    seconds: int
    side: str
    person: Person | None


@dataclass(frozen=True)
class Timeout:
    seconds: int
    side: str | None
    home: int
    away: int
    before: tuple[int, int]
    after: tuple[int, int]


@dataclass(frozen=True)
class MatchEvents:
    shots: tuple[Shot, ...]
    turnovers: tuple[Moment, ...]
    steals: tuple[Moment, ...]
    blocks: tuple[Moment, ...]
    suspensions: tuple[Moment, ...]
    red_cards: tuple[Moment, ...]
    timeouts: tuple[Moment, ...]
    end_seconds: int
    has_turnovers: bool
    has_steals: bool
    has_fast_breaks: bool
    yellow_cards: tuple[Moment, ...] = ()
    sevens_won: tuple[Moment, ...] = ()

    @property
    def goals(self) -> tuple[Shot, ...]:
        return tuple(shot for shot in self.shots if shot.is_goal)


def clean_actions(actions: Iterable[TickerAction]) -> tuple[TickerAction, ...]:
    """Drop the 7m shootout and events the feed repeats at the same moment and score."""
    kept: list[TickerAction] = []
    moment: tuple[int, int, int] | None = None
    seen: set[tuple] = set()
    for action in actions:
        if action.period in SHOOTOUT_PERIODS:
            continue
        here = (action.seconds, action.home, action.away)
        if here != moment:
            moment = here
            seen = set()
        zone = "FB" if action.zone in FAST_BREAK_ZONES else action.zone
        key = (action.code, action.result, zone, action.add, action.actors)
        if key in seen:
            continue
        seen.add(key)
        kept.append(action)
    return tuple(kept)


def match_events(actions: Iterable[TickerAction]) -> MatchEvents:
    cleaned = clean_actions(actions)
    shots: list[Shot] = []
    turnovers: list[Moment] = []
    steals: list[Moment] = []
    blocks: list[Moment] = []
    suspensions: list[Moment] = []
    red_cards: list[Moment] = []
    timeouts: list[Moment] = []
    yellow_cards: list[Moment] = []
    sevens_won: list[Moment] = []
    has_turnovers = has_steals = has_fast_breaks = False
    previous = (0, 0)
    for action in cleaned:
        code = action.code
        if code == "SHOT":
            shot = _shot(action, previous)
            has_fast_breaks = has_fast_breaks or action.zone in FAST_BREAK_ZONES
            if shot is not None:
                shots.append(shot)
            blocker = _actor(action, "BLC")
            if blocker is not None and action.result == "BLC":
                blocks.append(Moment(action.seconds, blocker.side, _person(blocker)))
        elif code == "TO" and action.add == "FB":
            has_fast_breaks = True
            _mark_fast_break(shots, action)
        elif code == "TO":
            has_turnovers = True
            moment = _moment(action, "TO")
            if moment is not None:
                turnovers.append(moment)
        elif code == "ST":
            has_steals = True
            moment = _moment(action, "ST")
            if moment is not None:
                steals.append(moment)
        elif code == "TMS":
            moment = _moment(action, None)
            if moment is not None:
                suspensions.append(moment)
        elif code == "RC":
            moment = _moment(action, None)
            if moment is not None:
                red_cards.append(moment)
        elif code == "YC":
            moment = _moment(action, None)
            if moment is not None:
                yellow_cards.append(moment)
        elif code == "RFP":
            moment = _moment(action, None)
            if moment is not None:
                sevens_won.append(moment)
        elif code == "TOUT" and action.add == "START":
            side = action.actors[0].side if action.actors else None
            timeouts.append(Moment(action.seconds, side or "", None))
        elif code == "GKS":
            has_fast_breaks = True
        previous = (action.home, action.away)
    last = max((action.seconds for action in cleaned), default=REGULATION)
    end = REGULATION if last <= REGULATION else REGULATION + 10 * 60
    return MatchEvents(
        shots=tuple(shots),
        turnovers=tuple(turnovers),
        steals=tuple(steals),
        blocks=tuple(blocks),
        suspensions=tuple(suspensions),
        red_cards=tuple(red_cards),
        timeouts=tuple(timeouts),
        end_seconds=end,
        has_turnovers=has_turnovers,
        has_steals=has_steals,
        has_fast_breaks=has_fast_breaks,
        yellow_cards=tuple(yellow_cards),
        sevens_won=tuple(sevens_won),
    )


def _actor(action: TickerAction, role: str) -> TickerActor | None:
    return next((actor for actor in action.actors if actor.role == role), None)


def _person(actor: TickerActor | None) -> Person | None:
    if actor is None or not (actor.name or actor.number):
        return None
    return Person(
        side=actor.side,
        number=(actor.number or "").strip(),
        name=(actor.name or "").strip(),
        person_id=actor.person_id,
    )


def _shot(action: TickerAction, previous: tuple[int, int]) -> Shot | None:
    shooter = _actor(action, "SCR")
    keeper = _actor(action, "GK")
    blocker = _actor(action, "BLC")
    if shooter is not None:
        side = shooter.side
    elif keeper is not None:
        side = _other(keeper.side)
    elif blocker is not None:
        side = _other(blocker.side)
    elif action.result == "GOAL" and action.home > previous[0]:
        side = "home"
    elif action.result == "GOAL" and action.away > previous[1]:
        side = "away"
    else:
        return None
    assist = _actor(action, "ASSIST") if action.result == "GOAL" else None
    return Shot(
        seconds=action.seconds,
        side=side,
        result=action.result or "",
        zone=action.zone,
        shooter=_person(shooter),
        keeper=_person(keeper) if keeper is not None and keeper.side != side else None,
        assist=_person(assist) if assist is not None and assist.side == side else None,
        home=action.home,
        away=action.away,
        fast_break=action.zone in FAST_BREAK_ZONES,
    )


def _mark_fast_break(shots: list[Shot], action: TickerAction) -> None:
    for index in range(len(shots) - 1, -1, -1):
        shot = shots[index]
        if shot.seconds != action.seconds:
            return
        if not action.actors or shot.side == action.actors[0].side:
            shots[index] = Shot(**{**shot.__dict__, "fast_break": True})
            return


def _moment(action: TickerAction, role: str | None) -> Moment | None:
    actor = (_actor(action, role) if role else None) or (action.actors[0] if action.actors else None)
    if actor is None:
        return None
    return Moment(action.seconds, actor.side, _person(actor))


def _other(side: str) -> str:
    return "away" if side == "home" else "home"


def _ratio(part: float, whole: float) -> float | None:
    return part / whole if whole else None


# --------------------------------------------------------------------------- team figures


@dataclass(frozen=True)
class TeamFigures:
    goals: int
    shots: int
    seven_goals: int
    seven_shots: int
    saves: int
    faced: int
    suspensions: int
    blocks: int
    assisted: int
    turnovers: int | None
    steals: int | None
    fast_breaks: int | None

    @property
    def shooting(self) -> float | None:
        return _ratio(self.goals, self.shots)

    @property
    def saving(self) -> float | None:
        return _ratio(self.saves, self.faced)

    @property
    def attack(self) -> float | None:
        if self.turnovers is None:
            return None
        return _ratio(self.goals, self.shots + self.turnovers)

    @property
    def assisted_share(self) -> float | None:
        return _ratio(self.assisted, self.goals)


def shot_zone_key(shot: Shot) -> str:
    """The zone an expected-goal rate is read for: fast breaks apart, then the throwing zone."""
    if shot.fast_break:
        return "FB"
    return shot.zone or "?"


def team_figures(events: MatchEvents, side: str) -> TeamFigures:
    own = [shot for shot in events.shots if shot.side == side]
    against = [shot for shot in events.shots if shot.side != side and shot.result in ("GOAL", "SAVE")]
    goals = [shot for shot in own if shot.is_goal]
    return TeamFigures(
        goals=len(goals),
        shots=len(own),
        seven_goals=sum(1 for shot in goals if shot.is_penalty),
        seven_shots=sum(1 for shot in own if shot.is_penalty),
        saves=sum(1 for shot in against if shot.result == "SAVE"),
        faced=len(against),
        suspensions=sum(1 for item in events.suspensions if item.side == side),
        blocks=sum(1 for item in events.blocks if item.side == side),
        assisted=sum(1 for shot in goals if shot.assist is not None),
        turnovers=sum(1 for item in events.turnovers if item.side == side) if events.has_turnovers else None,
        steals=sum(1 for item in events.steals if item.side == side) if events.has_steals else None,
        fast_breaks=sum(1 for shot in goals if shot.fast_break) if events.has_fast_breaks else None,
    )


@dataclass(frozen=True)
class Baseline:
    """Per team and match averages of the reference matches (ratios pooled over all shots)."""

    label: str
    matches: int
    values: dict[str, float]


def baseline(label: str, matches: Sequence[MatchEvents]) -> Baseline:
    sums: dict[str, list[float]] = {}

    def add(key: str, part: float | None, whole: float = 1.0) -> None:
        if part is None:
            return
        bucket = sums.setdefault(key, [0.0, 0.0])
        bucket[0] += part
        bucket[1] += whole

    for events in matches:
        for side in SIDES:
            team = team_figures(events, side)
            add("shooting", team.goals, team.shots)
            add("saving", team.saves, team.faced)
            add("seven", team.seven_goals)
            add("seven_shots", team.seven_shots)
            add("suspensions", team.suspensions)
            add("blocks", team.blocks)
            add("assisted", team.assisted, team.goals)
            add("goals", team.goals)
            if team.turnovers is not None:
                add("turnovers", team.turnovers)
                add("attack", team.goals, team.shots + team.turnovers)
            add("steals", team.steals)
            add("fast_breaks", team.fast_breaks)
        for shot in events.shots:
            zone = shot_zone_key(shot)
            add(f"zone_goal_{zone}", 1 if shot.is_goal else 0)
            add(f"zone_shots_{zone}", 1)
            if shot.result in ("GOAL", "SAVE"):
                add(f"zone_save_{zone}", 1 if shot.result == "SAVE" else 0, 1)
    for zone in {key.removeprefix("zone_shots_") for key in sums if key.startswith("zone_shots_")}:
        goals, shots = sums.get(f"zone_goal_{zone}", [0.0, 0.0])[0], sums[f"zone_shots_{zone}"][0]
        if shots:
            sums[f"xg_{zone}"] = [goals, shots]
    values = {key: part / whole for key, (part, whole) in sums.items() if whole and not key.startswith(("zone_goal_", "zone_shots_"))}
    return Baseline(label=label, matches=len(matches), values=values)


@dataclass(frozen=True)
class ComparisonRow:
    key: str
    home: float
    away: float
    home_text: str
    away_text: str
    average: float | None
    average_text: str
    scale: float
    better: str | None


def comparison(home: TeamFigures, away: TeamFigures, base: Baseline | None) -> tuple[ComparisonRow, ...]:
    avg = base.values if base else {}
    rows: list[ComparisonRow] = []

    def pct(label: str, key: str, h: float | None, a: float | None, detail: tuple[str, str] = ("", "")) -> None:
        if h is None or a is None:
            return
        average = avg.get(key)
        rows.append(
            ComparisonRow(
                key=label,
                home=h,
                away=a,
                home_text=f"{h:.0%}{detail[0]}",
                away_text=f"{a:.0%}{detail[1]}",
                average=average,
                average_text=f"{average:.0%}" if average is not None else "",
                scale=1.0,
                better=_better(h, a, True),
            )
        )

    def count(
        label: str,
        key: str,
        h: int | None,
        a: int | None,
        higher_is_better: bool = True,
        texts: tuple[str, str] | None = None,
    ) -> None:
        if h is None or a is None:
            return
        average = avg.get(key)
        rows.append(
            ComparisonRow(
                key=label,
                home=h,
                away=a,
                home_text=texts[0] if texts else str(h),
                away_text=texts[1] if texts else str(a),
                average=average,
                average_text=f"{average:.1f}" if average is not None else "",
                scale=max(h, a, average or 0, 1) * 1.1,
                better=_better(h, a, higher_is_better),
            )
        )

    pct("shooting", "shooting", home.shooting, away.shooting, (f" ({home.goals}/{home.shots})", f" ({away.goals}/{away.shots})"))
    pct("attack", "attack", home.attack, away.attack)
    pct("saving", "saving", home.saving, away.saving, (f" ({home.saves}/{home.faced})", f" ({away.saves}/{away.faced})"))
    count(
        "seven",
        "seven",
        home.seven_goals,
        away.seven_goals,
        texts=(f"{home.seven_goals}/{home.seven_shots}", f"{away.seven_goals}/{away.seven_shots}"),
    )
    count("fast_breaks", "fast_breaks", home.fast_breaks, away.fast_breaks)
    # assists depend on the ticker operator of the venue, so no competition average for them
    count("assisted", "", home.assisted, away.assisted)
    count("turnovers", "turnovers", home.turnovers, away.turnovers, higher_is_better=False)
    count("steals", "steals", home.steals, away.steals)
    count("blocks", "blocks", home.blocks, away.blocks)
    count("suspensions", "suspensions", home.suspensions, away.suspensions, higher_is_better=False)
    return tuple(rows)


def _better(home: float, away: float, higher_is_better: bool) -> str | None:
    if home == away:
        return None
    return "home" if (home > away) == higher_is_better else "away"


# --------------------------------------------------------------------------- shot maps


@dataclass(frozen=True)
class ZoneCell:
    zone: str
    goals: int
    shots: int

    @property
    def rate(self) -> float | None:
        return _ratio(self.goals, self.shots)


@dataclass(frozen=True)
class ShotMap:
    side: str
    cells: dict[str, ZoneCell]
    groups: tuple[ZoneCell, ...]
    fast_break: ZoneCell | None
    unplaced: int


def shot_map(events: MatchEvents, side: str) -> ShotMap:
    own = [shot for shot in events.shots if shot.side == side]

    def cell(name: str, zones: Iterable[str]) -> ZoneCell:
        wanted = set(zones)
        picked = [shot for shot in own if shot.zone in wanted]
        return ZoneCell(name, sum(1 for shot in picked if shot.is_goal), len(picked))

    breaks = [shot for shot in own if shot.fast_break]
    known = set(MAP_ZONES) | {PENALTY_ZONE} | FAST_BREAK_ZONES
    return ShotMap(
        side=side,
        cells={zone: cell(zone, (zone,)) for zone in MAP_ZONES},
        groups=tuple(cell(name, zones) for name, zones in ZONE_GROUPS),
        fast_break=ZoneCell("fast_break", sum(1 for s in breaks if s.is_goal), len(breaks))
        if events.has_fast_breaks or breaks
        else None,
        unplaced=sum(1 for shot in own if shot.zone not in known),
    )


# --------------------------------------------------------------------------- players


@dataclass
class PlayerLine:
    person: Person
    goals: int = 0
    shots: int = 0
    seven_goals: int = 0
    seven_shots: int = 0
    assists: int = 0
    turnovers: int = 0
    steals: int = 0
    suspensions: int = 0
    goal_seconds: list[int] = field(default_factory=list)

    @property
    def rate(self) -> float | None:
        return _ratio(self.goals, self.shots)


@dataclass
class KeeperLine:
    person: Person
    saves: int = 0
    faced: int = 0
    seven_saves: int = 0
    seven_faced: int = 0
    first: int = 0
    last: int = 0

    @property
    def rate(self) -> float | None:
        return _ratio(self.saves, self.faced)


def player_lines(events: MatchEvents, side: str) -> tuple[PlayerLine, ...]:
    lines: dict[Person, PlayerLine] = {}

    def line(person: Person | None) -> PlayerLine | None:
        if person is None or person.side != side:
            return None
        return lines.setdefault(person, PlayerLine(person))

    for shot in events.shots:
        shooter = line(shot.shooter)
        if shooter is not None:
            shooter.shots += 1
            shooter.seven_shots += shot.is_penalty
            if shot.is_goal:
                shooter.goals += 1
                shooter.seven_goals += shot.is_penalty
                shooter.goal_seconds.append(shot.seconds)
        helper = line(shot.assist) if shot.is_goal else None
        if helper is not None:
            helper.assists += 1
    for moment in events.turnovers:
        found = line(moment.person)
        if found is not None:
            found.turnovers += 1
    for moment in events.steals:
        found = line(moment.person)
        if found is not None:
            found.steals += 1
    for moment in events.suspensions:
        found = line(moment.person)
        if found is not None:
            found.suspensions += 1
    ordered = sorted(
        lines.values(),
        key=lambda p: (-p.goals, -(p.rate or 0), -p.assists, p.shots, _shirt(p.person.number)),
    )
    return tuple(ordered)


def keeper_lines(events: MatchEvents, side: str) -> tuple[KeeperLine, ...]:
    lines: dict[Person, KeeperLine] = {}
    for shot in events.shots:
        keeper = shot.keeper
        if keeper is None or keeper.side != side or shot.result not in ("GOAL", "SAVE"):
            continue
        line = lines.get(keeper)
        if line is None:
            line = lines[keeper] = KeeperLine(keeper, first=shot.seconds)
        line.faced += 1
        line.last = shot.seconds
        line.saves += shot.result == "SAVE"
        if shot.is_penalty:
            line.seven_faced += 1
            line.seven_saves += shot.result == "SAVE"
    return tuple(sorted(lines.values(), key=lambda k: k.first))


def _shirt(number: str) -> int:
    return int(number) if number.isdigit() else 999


# --------------------------------------------------------------------------- flow


@dataclass(frozen=True)
class Run:
    side: str
    goals: int
    conceded: int
    start: int
    end: int


@dataclass(frozen=True)
class Gap:
    side: str
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass(frozen=True)
class Lead:
    side: str
    margin: int
    seconds: int
    home: int
    away: int


@dataclass(frozen=True)
class Flow:
    goals: tuple[Shot, ...]
    end_seconds: int
    front: dict[str, int]
    ties: int
    lead_changes: int
    biggest: dict[str, Lead | None]
    runs: tuple[Run, ...]
    best_run: dict[str, Run | None]
    drought: dict[str, Gap | None]
    segments: tuple[tuple[str, int, int], ...]
    last_ten: tuple[int, int]
    timeouts: tuple[Timeout, ...]
    strength: dict[str, tuple[int, int, int, int]]


def match_flow(events: MatchEvents) -> Flow:
    goals = events.goals
    end = events.end_seconds
    front = {"home": 0, "away": 0, "tie": 0}
    ties = changes = 0
    leader: str | None = None
    biggest: dict[str, Lead | None] = {"home": None, "away": None}
    last_time = 0
    margin = 0
    for goal in goals:
        front[_state(margin)] += goal.seconds - last_time
        last_time = goal.seconds
        margin = goal.home - goal.away
        state = _state(margin)
        if state == "tie":
            ties += 1
        else:
            if leader is not None and state != leader:
                changes += 1
            leader = state
            current = biggest[state]
            if current is None or abs(margin) > current.margin:
                biggest[state] = Lead(state, abs(margin), goal.seconds, goal.home, goal.away)
    front[_state(margin)] += max(0, end - last_time)

    runs = _runs(goals)
    best_run = {side: max((r for r in runs if r.side == side), key=lambda r: (r.goals, -r.start), default=None) for side in SIDES}
    drought = {side: _longest_gap(goals, side, end) for side in SIDES}
    return Flow(
        goals=goals,
        end_seconds=end,
        front=front,
        ties=ties,
        lead_changes=changes,
        biggest=biggest,
        runs=tuple(r for r in runs if r.goals >= MIN_RUN),
        best_run=best_run,
        drought=drought,
        segments=_segments(goals, end),
        last_ten=_count(goals, REGULATION - 600, REGULATION),
        timeouts=_timeouts(events, goals),
        strength={side: _strength(events, goals, side) for side in SIDES},
    )


def _state(margin: int) -> str:
    return "home" if margin > 0 else "away" if margin < 0 else "tie"


def _runs(goals: Sequence[Shot]) -> list[Run]:
    """Unanswered scoring spells (opponent goals in between end the run)."""
    runs: list[Run] = []
    start = 0
    for index in range(1, len(goals) + 1):
        if index == len(goals) or goals[index].side != goals[start].side:
            if goals:
                runs.append(Run(goals[start].side, index - start, 0, goals[start].seconds, goals[index - 1].seconds))
            start = index
    return runs


def _longest_gap(goals: Sequence[Shot], side: str, end: int) -> Gap | None:
    times = [0] + [goal.seconds for goal in goals if goal.side == side] + [end]
    gaps = [Gap(side, a, b) for a, b in zip(times, times[1:])]
    return max(gaps, key=lambda g: g.length, default=None)


def _count(goals: Sequence[Shot], start: int, end: int) -> tuple[int, int]:
    inside = [goal for goal in goals if start < goal.seconds <= end or (start == 0 and goal.seconds == 0)]
    return (sum(1 for g in inside if g.side == "home"), sum(1 for g in inside if g.side == "away"))


def _segments(goals: Sequence[Shot], end: int) -> tuple[tuple[str, int, int], ...]:
    parts = []
    for start in range(0, REGULATION, 600):
        home, away = _count(goals, start, start + 600)
        parts.append((f"{start // 60}–{start // 60 + 10}'", home, away))
    if end > REGULATION:
        home, away = _count(goals, REGULATION, end)
        parts.append(("ET", home, away))
    return tuple(parts)


def _timeouts(events: MatchEvents, goals: Sequence[Shot]) -> tuple[Timeout, ...]:
    items = []
    for moment in events.timeouts:
        score = (0, 0)
        for goal in goals:
            if goal.seconds <= moment.seconds:
                score = (goal.home, goal.away)
        before = _count(goals, max(0, moment.seconds - TIMEOUT_WINDOW), moment.seconds)
        after = _count(goals, moment.seconds, moment.seconds + TIMEOUT_WINDOW)
        items.append(Timeout(moment.seconds, moment.side or None, score[0], score[1], before, after))
    return tuple(items)


def _strength(events: MatchEvents, goals: Sequence[Shot], side: str) -> tuple[int, int, int, int]:
    """Goals for/against with more players on court, then for/against with fewer players."""
    windows = [(m.side, m.seconds, m.seconds + SUSPENSION_SECONDS) for m in events.suspensions + events.red_cards]

    def short(team: str, t: int) -> int:
        return sum(1 for owner, a, b in windows if owner == team and a < t <= b)

    up_for = up_against = down_for = down_against = 0
    for goal in goals:
        balance = short(_other(side), goal.seconds) - short(side, goal.seconds)
        mine = goal.side == side
        if balance > 0:
            up_for += mine
            up_against += not mine
        elif balance < 0:
            down_for += mine
            down_against += not mine
    return up_for, up_against, down_for, down_against


# --------------------------------------------------------------------------- win probability


def win_probability(margin: int, seconds_left: int) -> float:
    minutes = max(0, seconds_left) / 60
    x = WIN_LEAD * margin / math.sqrt(minutes + 1) + WIN_HOME * math.sqrt(minutes / 60)
    return 1 / (1 + math.exp(-x))


@dataclass(frozen=True)
class KeyMoment:
    seconds: int
    side: str
    scorer: Person | None
    home: int
    away: int
    before: float
    after: float


@dataclass(frozen=True)
class WinCurve:
    points: tuple[tuple[int, float], ...]
    moments: tuple[KeyMoment, ...]


def win_curve(goals: Sequence[Shot], end: int, final_home: int, final_away: int, step: int = 15) -> WinCurve:
    """Home win probability every ``step`` seconds and just after each goal; the last point is the result."""
    points: list[tuple[int, float]] = []
    moments: list[KeyMoment] = []
    margin = 0
    index = 0
    for t in range(0, end, step):
        while index < len(goals) and goals[index].seconds <= t:
            goal = goals[index]
            before = win_probability(margin, end - goal.seconds)
            margin = goal.home - goal.away
            after = win_probability(margin, end - goal.seconds)
            points.append((goal.seconds, before))
            points.append((goal.seconds, after))
            moments.append(KeyMoment(goal.seconds, goal.side, goal.shooter, goal.home, goal.away, before, after))
            index += 1
        points.append((t, win_probability(margin, end - t)))
    while index < len(goals):
        goal = goals[index]
        before = win_probability(margin, end - goal.seconds)
        margin = goal.home - goal.away
        after = win_probability(margin, end - goal.seconds)
        points.extend(((goal.seconds, before), (goal.seconds, after)))
        moments.append(KeyMoment(goal.seconds, goal.side, goal.shooter, goal.home, goal.away, before, after))
        index += 1
    result = 1.0 if final_home > final_away else 0.0 if final_home < final_away else 0.5
    points.append((end, result))
    points.sort(key=lambda p: p[0])
    top = sorted(moments, key=lambda m: abs(m.after - m.before), reverse=True)[:KEY_MOMENTS]
    return WinCurve(points=tuple(points), moments=tuple(sorted(top, key=lambda m: m.seconds)))


# --------------------------------------------------------------------------- story


def clock(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def minute(seconds: int) -> str:
    return f"{max(1, math.ceil(seconds / 60))}'"


@dataclass(frozen=True)
class Headline:
    """What the opening sentence says; the wording (and language) is left to the page.

    kind: ``shootout``, ``draw``, ``comeback``, ``control``, ``go_ahead`` or ``plain``.
    """

    kind: str
    winner: str | None
    values: dict[str, object]


def headline(flow: Flow, final: tuple[int, int], regular: tuple[int, int], shootout: bool) -> Headline:
    home, away = final
    totals = {"ties": flow.ties, "changes": flow.lead_changes}
    if shootout:
        winner = "home" if home > away else "away"
        regular_text = _winner_first(regular[0], regular[1], winner)
        return Headline("shootout", winner, {**totals, "regular": regular_text, "extra_time": flow.end_seconds > REGULATION})
    if home == away:
        return Headline("draw", None, {**totals, "score": f"{home}:{away}"})
    winner = "home" if home > away else "away"
    margin = abs(home - away)
    score = _winner_first(home, away, winner)
    deficit = _late_deficit(flow.goals, winner)
    if deficit is not None:
        after = [g for g in flow.goals if g.seconds > deficit.seconds]
        scored = sum(1 for g in after if g.side == winner)
        return Headline(
            "comeback",
            winner,
            {
                "behind": _winner_first(deficit.home, deficit.away, winner),
                "clock": clock(deficit.seconds),
                "minute": deficit.seconds // 60 + 1,
                "score": score,
                "finish": f"{scored}:{len(after) - scored}",
            },
        )
    lead = flow.biggest[winner]
    if margin >= 6 or flow.front[winner] >= 45 * 60:
        return Headline(
            "control",
            winner,
            {
                "front": flow.front[winner] // 60,
                "total": flow.end_seconds // 60,
                "margin": margin,
                "score": score,
                "lead": lead.margin if lead else None,
                "lead_clock": clock(lead.seconds) if lead else None,
                "lead_minute": lead.seconds // 60 + 1 if lead else None,
            },
        )
    decider = _go_ahead(flow.goals, winner)
    if decider is not None and decider.shooter is not None:
        return Headline(
            "go_ahead",
            winner,
            {
                "score": score,
                "scorer": decider.shooter.name,
                "clock": clock(decider.seconds),
                "minute": decider.seconds // 60 + 1,
                "at": _winner_first(decider.home, decider.away, winner),
            },
        )
    return Headline("plain", winner, {"score": score})


def _winner_first(home: int, away: int, winner: str) -> str:
    """A score as the winner sees it ("33:30" for an away win 30:33)."""
    return f"{home}:{away}" if winner == "home" else f"{away}:{home}"


def _late_deficit(goals: Sequence[Shot], winner: str) -> Shot | None:
    """The goal that left the winner furthest behind (2+) after half-time; the latest of equals."""
    worst = None
    worst_margin = -1
    for goal in goals:
        margin = (goal.home - goal.away) * (1 if winner == "home" else -1)
        if goal.seconds >= HALF and margin <= -2 and margin <= worst_margin:
            worst, worst_margin = goal, margin
    return worst


def _go_ahead(goals: Sequence[Shot], winner: str) -> Shot | None:
    """The goal after which the winner never again failed to lead."""
    decider = None
    for goal in goals:
        state = _state(goal.home - goal.away)
        if state != winner:
            decider = None
        elif decider is None:
            decider = goal
    return decider


# --------------------------------------------------------------------------- the page


@dataclass(frozen=True)
class SummaryHeader:
    match_id: int
    competition_id: int
    competition_name: str
    season_code: str
    year_start: int
    phase: str | None
    group_code: str | None
    kickoff_at: object
    venue_name: str | None
    venue_city: str | None
    spectators: int | None
    home_name: str
    away_name: str
    home_logo: str | None
    away_logo: str | None
    score_home: int
    score_away: int
    half_time_home: int | None
    half_time_away: int | None
    extra_time: bool
    shootout: bool

    @property
    def names(self) -> dict[str, str]:
        return {"home": self.home_name, "away": self.away_name}


@dataclass(frozen=True)
class Fact:
    key: str
    home: str
    away: str
    detail_home: str = ""
    detail_away: str = ""


@dataclass(frozen=True)
class MatchSummary:
    header: SummaryHeader
    headline: Headline
    flow: Flow
    win: WinCurve
    figures: dict[str, TeamFigures]
    comparison: tuple[ComparisonRow, ...]
    baseline: Baseline | None
    maps: dict[str, ShotMap]
    players: dict[str, tuple[PlayerLine, ...]]
    keepers: dict[str, tuple[KeeperLine, ...]]
    facts: tuple[Fact, ...]
    regular_score: tuple[int, int]
    has_turnovers: bool
    suspensions: tuple[Moment, ...]
    red_cards: tuple[Moment, ...]


def build_summary(header: SummaryHeader, actions: Sequence[TickerAction], base: Baseline | None) -> MatchSummary:
    events = match_events(actions)
    flow = match_flow(events)
    final = (header.score_home, header.score_away)
    regular = (flow.goals[-1].home, flow.goals[-1].away) if flow.goals else (0, 0)
    figures = {side: team_figures(events, side) for side in SIDES}
    return MatchSummary(
        header=header,
        headline=headline(flow, final, regular, header.shootout),
        flow=flow,
        win=win_curve(flow.goals, flow.end_seconds, *(regular if header.shootout else final)),
        figures=figures,
        comparison=comparison(figures["home"], figures["away"], base),
        baseline=base,
        maps={side: shot_map(events, side) for side in SIDES},
        players={side: player_lines(events, side) for side in SIDES},
        keepers={side: keeper_lines(events, side) for side in SIDES},
        facts=facts(flow),
        regular_score=regular,
        has_turnovers=events.has_turnovers,
        suspensions=events.suspensions,
        red_cards=events.red_cards,
    )


def facts(flow: Flow) -> tuple[Fact, ...]:
    def lead(side: str) -> tuple[str, str]:
        item = flow.biggest[side]
        return (f"+{item.margin}", f"{item.home}:{item.away} · {minute(item.seconds)}") if item else ("–", "")

    def run(side: str) -> tuple[str, str]:
        item = flow.best_run[side]
        if item is None:
            return "–", ""
        span = minute(item.start) if item.start // 60 == item.end // 60 else f"{minute(item.start)}–{minute(item.end)}"
        return f"{item.goals}:0", span

    def gap(side: str) -> tuple[str, str]:
        item = flow.drought[side]
        return (clock(item.length), f"{minute(item.start) if item.start else '0'}–{minute(item.end)}") if item else ("–", "")

    def pair(key: str, values) -> Fact:
        (h, dh), (a, da) = values("home"), values("away")
        return Fact(key, h, a, dh, da)

    return (
        Fact("front", clock(flow.front["home"]), clock(flow.front["away"])),
        pair("biggest_lead", lead),
        pair("best_run", run),
        pair("drought", gap),
        Fact("last_ten", str(flow.last_ten[0]), str(flow.last_ten[1])),
    )
